from __future__ import annotations

from confluent_kafka.schema_registry import SchemaRegistryClient


def build_sr_client(url: str) -> SchemaRegistryClient:
    return SchemaRegistryClient({"url": url})
