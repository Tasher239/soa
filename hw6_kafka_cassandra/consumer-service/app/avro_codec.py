from __future__ import annotations

import io
import json
import logging
import struct
from typing import Any

from confluent_kafka.schema_registry import Schema, SchemaRegistryClient
from fastavro import parse_schema, schemaless_reader, schemaless_writer

log = logging.getLogger(__name__)

_MAGIC_BYTE = 0


class AvroCodec:
    def __init__(self, registry_url: str, topic: str) -> None:
        self._sr = SchemaRegistryClient({"url": registry_url})
        self._topic = topic
        self._writer_schemas: dict[int, dict[str, Any]] = {}
        self._writer_names: dict[int, str] = {}

    def _load_schema(self, schema_id: int) -> tuple[dict[str, Any], str]:
        if schema_id in self._writer_schemas:
            return self._writer_schemas[schema_id], self._writer_names[schema_id]
        raw = self._sr.get_schema(schema_id).schema_str
        schema_dict = json.loads(raw)
        if schema_dict.get("type") != "record":
            raise ValueError(f"unsupported top-level avro type: {schema_dict.get('type')}")
        name = schema_dict["name"]
        parsed = parse_schema(schema_dict)
        self._writer_schemas[schema_id] = parsed
        self._writer_names[schema_id] = name
        log.info("cached writer schema id=%s name=%s", schema_id, name)
        return parsed, name

    def deserialize(self, raw: bytes) -> tuple[str, dict[str, Any], int]:
        if raw is None or len(raw) < 5:
            raise ValueError("payload too short for confluent wire format")
        magic, schema_id = struct.unpack(">bI", raw[:5])
        if magic != _MAGIC_BYTE:
            raise ValueError(f"unexpected magic byte {magic}")
        parsed, name = self._load_schema(schema_id)
        record = schemaless_reader(io.BytesIO(raw[5:]), parsed)
        return name, record, schema_id

    def serialize(self, record: dict[str, Any], schema_str: str, record_name: str) -> bytes:
        subject = f"{self._topic}-{record_name}"
        schema = Schema(schema_str, schema_type="AVRO")
        schema_id = self._sr.register_schema(subject, schema)
        parsed = parse_schema(json.loads(schema_str))
        buf = io.BytesIO()
        buf.write(struct.pack(">bI", _MAGIC_BYTE, schema_id))
        schemaless_writer(buf, parsed, record)
        return buf.getvalue()
