"""Integration test: POST /events → Avro message arrives in Kafka topic."""
from __future__ import annotations

import time
import uuid

import httpx
import pytest
from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import MessageField, SerializationContext

from conftest import KAFKA_BOOTSTRAP_SERVERS, PRODUCER_URL, SCHEMA_REGISTRY_URL, unique_id

TOPIC = "movie-events"


def _wait_for_assignment(consumer: Consumer, deadline_sec: float = 30.0) -> None:
    """Subscribe + poll until partitions are assigned (rebalance done)."""
    deadline = time.time() + deadline_sec
    while time.time() < deadline:
        consumer.poll(timeout=0.5)
        if consumer.assignment():
            return
    raise AssertionError(
        f"Consumer did not get partition assignment for topic '{TOPIC}' within {deadline_sec}s"
    )


@pytest.fixture
def avro_consumer():
    sr = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
    deserializer = AvroDeserializer(schema_registry_client=sr)
    group_id = f"test-{unique_id()}"
    c = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": group_id,
        # 'latest' so we don't drown in old events from the producer generator
        "auto.offset.reset": "latest",
        "enable.auto.commit": False,
        "session.timeout.ms": 10000,
    })
    c.subscribe([TOPIC])
    _wait_for_assignment(c)
    yield c, deserializer
    c.close()


def _poll_avro_until_found(
    consumer: Consumer,
    deserializer: AvroDeserializer,
    predicate,
    timeout_sec: float = 60.0,
):
    """Poll until predicate(value) returns truthy. Returns the matching value or None."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        msg = consumer.poll(timeout=1.0)
        if msg is None or msg.error():
            continue
        ctx = SerializationContext(msg.topic(), MessageField.VALUE)
        try:
            value = deserializer(msg.value(), ctx)
        except Exception:
            continue
        if value is not None and predicate(value):
            return value
    return None


@pytest.mark.asyncio
async def test_published_event_reaches_kafka(avro_consumer):
    consumer, deserializer = avro_consumer
    cid = unique_id()
    user_id = f"integ_user_{cid}"
    movie_id = f"movie_{cid}"
    payload = {
        "user_id": user_id,
        "movie_id": movie_id,
        "event_type": "VIEW_STARTED",
        "device_type": "MOBILE",
        "session_id": f"sess_{cid}",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{PRODUCER_URL}/events", json=payload)
    assert r.status_code == 201, r.text
    event_id = r.json()["event_id"]
    assert uuid.UUID(event_id)

    found = _poll_avro_until_found(
        consumer,
        deserializer,
        predicate=lambda v: v.get("user_id") == user_id and v.get("movie_id") == movie_id,
        timeout_sec=60.0,
    )
    assert found is not None, f"Event user={user_id} not found in Kafka within 60s"
    assert found["event_type"] == "VIEW_STARTED"
    assert found["device_type"] == "MOBILE"
    assert str(found["event_id"]) == event_id


@pytest.mark.asyncio
async def test_batch_publish_all_reach_kafka(avro_consumer):
    consumer, deserializer = avro_consumer
    tag = unique_id()
    expected_movie = f"m_{tag}"
    events = [
        {
            "user_id": f"batch_{tag}_{i}",
            "movie_id": expected_movie,
            "event_type": "LIKED",
            "device_type": "DESKTOP",
            "session_id": f"s_{tag}_{i}",
        }
        for i in range(5)
    ]

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{PRODUCER_URL}/events/batch", json={"events": events})
    assert r.status_code == 200
    body = r.json()
    assert body["succeeded"] == 5

    seen_user_ids: set[str] = set()
    deadline = time.time() + 90.0
    while time.time() < deadline and len(seen_user_ids) < 5:
        msg = consumer.poll(timeout=1.0)
        if msg is None or msg.error():
            continue
        ctx = SerializationContext(msg.topic(), MessageField.VALUE)
        try:
            value = deserializer(msg.value(), ctx)
        except Exception:
            continue
        if value and value.get("movie_id") == expected_movie:
            seen_user_ids.add(value.get("user_id"))

    assert len(seen_user_ids) >= 5, (
        f"Only {len(seen_user_ids)}/5 batch events found in Kafka. Seen: {seen_user_ids}"
    )
