from __future__ import annotations

import logging
import threading
import time
from typing import Any

from confluent_kafka import Consumer, KafkaException, TopicPartition

from .avro_codec import AvroCodec
from .cassandra_client import CassandraClient
from .config import settings
from .dlq import DLQPublisher
from .handlers import (
    HANDLERS,
    NAME_TO_EVENT_TYPE,
    OutOfOrder,
    ValidationError,
)
from . import metrics

log = logging.getLogger(__name__)


class WarehouseConsumer:
    def __init__(self, cassandra: CassandraClient) -> None:
        self._cassandra = cassandra
        self._codec = AvroCodec(settings.schema_registry_url, settings.kafka_topic)
        self._dlq = DLQPublisher()
        self._consumer = Consumer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_group_id,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "partition.assignment.strategy": "cooperative-sticky",
            "session.timeout.ms": 30000,
        })
        self._stopping = threading.Event()
        self._lag_thread: threading.Thread | None = None
        self._healthy = True

    def start(self) -> None:
        self._consumer.subscribe([settings.kafka_topic])
        self._lag_thread = threading.Thread(target=self._lag_loop, daemon=True)
        self._lag_thread.start()
        try:
            self._run()
        finally:
            self.close()

    def stop(self) -> None:
        self._stopping.set()

    def close(self) -> None:
        try:
            self._consumer.close()
        except Exception:
            pass
        self._dlq.flush()

    def is_kafka_healthy(self) -> bool:
        return self._healthy

    def _run(self) -> None:
        log.info("consumer started, topic=%s group=%s", settings.kafka_topic, settings.kafka_group_id)
        while not self._stopping.is_set():
            msg = self._consumer.poll(settings.poll_timeout_seconds)
            if msg is None:
                continue
            if msg.error():
                log.error("kafka error: %s", msg.error())
                self._healthy = False
                continue
            self._healthy = True
            self._process(msg)

    def _process(self, msg) -> None:
        topic = msg.topic()
        partition = msg.partition()
        offset = msg.offset()
        raw = msg.value()

        try:
            record_name, event, schema_id = self._codec.deserialize(raw)
        except Exception as exc:
            log.exception("deserialize failed")
            metrics.events_dlq_total.labels(error_code="DESERIALIZATION_ERROR").inc()
            self._dlq.publish(
                original_event=None,
                raw_value=raw,
                error_reason=f"deserialization failed: {exc}",
                error_code="DESERIALIZATION_ERROR",
                partition=partition,
                offset=offset,
                topic=topic,
            )
            self._commit(msg)
            return

        handler = HANDLERS.get(record_name)
        event_type = NAME_TO_EVENT_TYPE.get(record_name, record_name)
        if handler is None:
            metrics.events_dlq_total.labels(error_code="UNKNOWN_EVENT_TYPE").inc()
            self._dlq.publish(
                original_event=event,
                raw_value=raw,
                error_reason=f"no handler for record {record_name}",
                error_code="UNKNOWN_EVENT_TYPE",
                partition=partition,
                offset=offset,
                topic=topic,
            )
            self._commit(msg)
            return

        event_id = event.get("event_id")
        if event_id and self._cassandra.is_event_processed(event_id):
            log.info("skip duplicate event event_id=%s type=%s offset=%s partition=%s",
                     event_id, event_type, offset, partition)
            metrics.events_skipped_total.labels(event_type=event_type, reason="duplicate").inc()
            self._commit(msg)
            return

        timer = metrics.event_processing_duration_seconds.labels(event_type=event_type)
        with timer.time():
            try:
                handler(self._cassandra, event)
            except OutOfOrder as exc:
                log.info("skip out-of-order event event_id=%s type=%s reason=%s",
                         event_id, event_type, exc)
                metrics.events_skipped_total.labels(event_type=event_type, reason="out_of_order").inc()
                self._commit(msg)
                return
            except ValidationError as exc:
                log.warning("validation failed event_id=%s type=%s: %s",
                            event_id, event_type, exc.reason)
                metrics.events_dlq_total.labels(error_code=exc.code).inc()
                self._dlq.publish(
                    original_event=event,
                    raw_value=raw,
                    error_reason=exc.reason,
                    error_code=exc.code,
                    partition=partition,
                    offset=offset,
                    topic=topic,
                )
                self._commit(msg)
                return
            except Exception as exc:
                log.exception("transient error processing event_id=%s type=%s",
                              event_id, event_type)
                metrics.cassandra_write_errors_total.inc()
                time.sleep(1.0)
                return

        metrics.events_processed_total.labels(event_type=event_type).inc()
        log.info("processed event_id=%s type=%s partition=%s offset=%s",
                 event_id, event_type, partition, offset)
        self._commit(msg)

    def _commit(self, msg) -> None:
        try:
            self._consumer.commit(message=msg, asynchronous=False)
        except KafkaException as exc:
            log.error("commit failed: %s", exc)

    def _lag_loop(self) -> None:
        while not self._stopping.is_set():
            try:
                self._refresh_lag()
            except Exception:
                log.exception("lag refresh failed")
            self._stopping.wait(settings.lag_refresh_seconds)

    def _refresh_lag(self) -> None:
        assignment = self._consumer.assignment()
        if not assignment:
            return
        for tp in assignment:
            low, high = self._consumer.get_watermark_offsets(tp, timeout=2.0, cached=False)
            committed = self._consumer.committed([tp], timeout=2.0)[0]
            committed_offset = committed.offset if committed and committed.offset >= 0 else low
            lag = max(0, high - committed_offset)
            metrics.consumer_lag.labels(topic=tp.topic, partition=str(tp.partition)).set(lag)
