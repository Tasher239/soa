from __future__ import annotations

import io
import json
import logging
import os
import struct
from pathlib import Path
from typing import Any

from confluent_kafka import Producer
from confluent_kafka.schema_registry import Schema, SchemaRegistryClient
from fastavro import parse_schema, schemaless_writer

from .config import settings

log = logging.getLogger(__name__)

_MAGIC_BYTE = 0


class WarehouseProducer:
    def __init__(self) -> None:
        self._sr = SchemaRegistryClient({"url": settings.schema_registry_url})
        self._producer = Producer({
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "enable.idempotence": True,
            "acks": "all",
            "compression.type": "lz4",
        })
        self._cache: dict[str, tuple[int, dict[str, Any]]] = {}
        self._schemas_dir = Path(settings.schemas_dir)

    def _load_schema_file(self, filename: str) -> str:
        return (self._schemas_dir / filename).read_text(encoding="utf-8")

    def _register(self, record_name: str, schema_str: str) -> tuple[int, dict[str, Any]]:
        subject = f"{settings.kafka_topic}-{record_name}"
        schema = Schema(schema_str, schema_type="AVRO")
        schema_id = self._sr.register_schema(subject, schema)
        parsed = parse_schema(json.loads(schema_str))
        return schema_id, parsed

    def ensure_schema(self, record_name: str, schema_filename: str) -> tuple[int, dict[str, Any]]:
        cache_key = f"{record_name}:{schema_filename}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        schema_str = self._load_schema_file(schema_filename)
        schema_id, parsed = self._register(record_name, schema_str)
        self._cache[cache_key] = (schema_id, parsed)
        log.info("registered schema subject=%s-%s id=%s", settings.kafka_topic, record_name, schema_id)
        return schema_id, parsed

    def register_all(self) -> dict[str, int]:
        v1_id, _ = self.ensure_schema("ProductReceived", "product_received_v1.avsc")
        v2_id, _ = self.ensure_schema("ProductReceived", "product_received_v2.avsc")
        result: dict[str, int] = {
            "ProductReceived.v1": v1_id,
            "ProductReceived.v2": v2_id,
        }
        for record, filename in {
            "ProductShipped": "product_shipped.avsc",
            "ProductMoved": "product_moved.avsc",
            "ProductReserved": "product_reserved.avsc",
            "ProductReleased": "product_released.avsc",
            "InventoryCounted": "inventory_counted.avsc",
            "OrderCreated": "order_created.avsc",
            "OrderCompleted": "order_completed.avsc",
        }.items():
            schema_id, _ = self.ensure_schema(record, filename)
            result[record] = schema_id
        return result

    def publish(self, record_name: str, schema_filename: str, record: dict[str, Any],
                key: str | None = None) -> tuple[int, int, int]:
        schema_id, parsed = self.ensure_schema(record_name, schema_filename)
        buf = io.BytesIO()
        buf.write(struct.pack(">bI", _MAGIC_BYTE, schema_id))
        schemaless_writer(buf, parsed, record)

        delivered: dict[str, Any] = {}

        def _cb(err, msg):
            if err is not None:
                delivered["error"] = str(err)
            else:
                delivered["partition"] = msg.partition()
                delivered["offset"] = msg.offset()

        self._producer.produce(
            settings.kafka_topic,
            value=buf.getvalue(),
            key=key.encode("utf-8") if key else None,
            on_delivery=_cb,
        )
        self._producer.flush(10)
        if "error" in delivered:
            raise RuntimeError(f"kafka produce failed: {delivered['error']}")
        return delivered["partition"], delivered["offset"], schema_id

    def publish_raw(self, raw: bytes, key: str | None = None) -> None:
        self._producer.produce(
            settings.kafka_topic,
            value=raw,
            key=key.encode("utf-8") if key else None,
        )
        self._producer.flush(10)

    def close(self) -> None:
        self._producer.flush(10)
