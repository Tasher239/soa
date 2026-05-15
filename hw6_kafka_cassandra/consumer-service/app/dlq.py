from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from confluent_kafka import Producer

from .config import settings

log = logging.getLogger(__name__)


class DLQPublisher:
    def __init__(self) -> None:
        self._producer = Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
            "compression.type": "lz4",
        })

    def publish(
        self,
        *,
        original_event: dict[str, Any] | None,
        raw_value: bytes | None,
        error_reason: str,
        error_code: str,
        partition: int,
        offset: int,
        topic: str,
    ) -> None:
        body = {
            "original_event": original_event,
            "raw_value_b64": None if raw_value is None else raw_value.hex(),
            "error_reason": error_reason,
            "error_code": error_code,
            "failed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "kafka_metadata": {
                "topic": topic,
                "partition": partition,
                "offset": offset,
            },
        }
        payload = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self._producer.produce(settings.kafka_dlq_topic, value=payload)
        self._producer.poll(0)
        log.warning("event sent to DLQ: code=%s reason=%s", error_code, error_reason)

    def flush(self) -> None:
        self._producer.flush(10)
