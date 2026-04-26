from __future__ import annotations

import asyncio
import threading
from typing import Any

from confluent_kafka import Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer
from confluent_kafka.serialization import MessageField, SerializationContext

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from cinema_shared.logging import get_logger
from cinema_shared.schemas.events import MovieEvent

from app.core.config import settings
from app.domain.exceptions import PublishFailed

from app.infra.exposition.metrics import EVENTS_FAILED, EVENTS_PRODUCED, PUBLISH_LATENCY

logger = get_logger("producer.kafka")

class AvroKafkaProducer:
    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        schema_registry_url: str,
        avro_schema_str: str,
    ) -> None:
        self._topic = topic
        self._loop: asyncio.AbstractEventLoop | None = None

        producer_conf = {
            "bootstrap.servers": bootstrap_servers,
            "client.id": "cinema-producer",
            "acks": settings.kafka_acks,
            "enable.idempotence": settings.kafka_enable_idempotence,
            "max.in.flight.requests.per.connection": settings.kafka_max_in_flight,
            "compression.type": settings.kafka_compression_type,
            "linger.ms": settings.kafka_linger_ms,
            "batch.size": settings.kafka_batch_size,
            "queue.buffering.max.kbytes": settings.kafka_queue_buffer_kb,
            "delivery.timeout.ms": settings.kafka_delivery_timeout_ms,
            "retries": 2_147_483_647,
            "retry.backoff.ms": 100,
        }
        self._producer = Producer(producer_conf)

        sr = SchemaRegistryClient({"url": schema_registry_url})
        self._serializer = AvroSerializer(
            schema_registry_client=sr,
            schema_str=avro_schema_str,
            conf={"auto.register.schemas": True, "use.latest.version": False},
        )

        self._stop = threading.Event()
        self._poll_thread: threading.Thread | None = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._stop.clear()
        self._poll_thread = threading.Thread(
            target=self._poll_loop, name="kafka-producer-poll", daemon=True
        )
        self._poll_thread.start()
        logger.info("kafka_producer_started", topic=self._topic)

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            self._producer.poll(0.1)
        self._producer.poll(0)

    async def stop(self, timeout: float = 10.0) -> None:
        logger.info("kafka_producer_stopping")
        await asyncio.get_event_loop().run_in_executor(None, self._producer.flush, timeout)
        self._stop.set()
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=2)
        logger.info("kafka_producer_stopped")

    def _make_delivery_cb(self, future: asyncio.Future) -> Any:
        loop = self._loop
        assert loop is not None

        def _cb(err, msg):
            if err is not None:
                if not future.done():
                    loop.call_soon_threadsafe(future.set_exception, KafkaDeliveryError(str(err)))
            else:
                if not future.done():
                    loop.call_soon_threadsafe(
                        future.set_result,
                        {
                            "topic": msg.topic(),
                            "partition": msg.partition(),
                            "offset": msg.offset(),
                        },
                    )

        return _cb

    async def _produce_once(self, event: MovieEvent) -> dict[str, Any]:
        assert self._loop is not None
        future: asyncio.Future = self._loop.create_future()
        avro_value = event.to_avro_dict()
        ctx = SerializationContext(self._topic, MessageField.VALUE)
        try:
            payload = self._serializer(avro_value, ctx)
        except Exception as exc:
            raise KafkaDeliveryError(f"avro_serialization_failed: {exc}") from exc

        try:
            self._producer.produce(
                topic=self._topic,
                key=event.user_id.encode("utf-8"),
                value=payload,
                on_delivery=self._make_delivery_cb(future),
            )
        except BufferError as exc:
            raise KafkaDeliveryError(f"producer_queue_full: {exc}") from exc

        return await future

    @PUBLISH_LATENCY.time()
    async def publish(self, event: MovieEvent) -> dict[str, Any]:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.retry_attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=settings.retry_min_seconds,
                    max=settings.retry_max_seconds,
                ),
                retry=retry_if_exception_type(KafkaDeliveryError),
                reraise=True,
            ):
                with attempt:
                    result = await self._produce_once(event)
        except RetryError as exc:
            EVENTS_FAILED.labels(str(event.event_type), "retries_exhausted").inc()
            raise PublishFailed("exhausted delivery retries", {"cause": str(exc)}) from exc
        except KafkaDeliveryError as exc:
            EVENTS_FAILED.labels(str(event.event_type), "delivery_error").inc()
            raise PublishFailed(str(exc)) from exc

        EVENTS_PRODUCED.labels(str(event.event_type)).inc()
        logger.info(
            "event_published",
            **event.log_fields(),
            partition=result.get("partition"),
            offset=result.get("offset"),
        )
        return result

    async def healthy(self) -> bool:
        loop = asyncio.get_event_loop()

        def _probe() -> bool:
            try:
                md = self._producer.list_topics(timeout=3.0)
                return bool(md.topics)
            except Exception:
                return False

        return await loop.run_in_executor(None, _probe)


class KafkaDeliveryError(RuntimeError):
    pass