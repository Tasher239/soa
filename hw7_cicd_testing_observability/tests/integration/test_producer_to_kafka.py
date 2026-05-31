from __future__ import annotations

import uuid

import httpx
import pytest
from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import MessageField, SerializationContext

from conftest import KAFKA_BOOTSTRAP_SERVERS, PRODUCER_URL, SCHEMA_REGISTRY_URL, unique_id


@pytest.fixture
def avro_consumer():
    sr = SchemaRegistryClient({"url": SCHEMA_REGISTRY_URL})
    deserializer = AvroDeserializer(schema_registry_client=sr)
    group_id = f"test-{unique_id()}"
    c = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    c.subscribe(["movie-events"])
    yield c, deserializer
    c.close()


def _poll_avro(consumer: Consumer, deserializer: AvroDeserializer, timeout_iters: int = 60):
    """Yield deserialized dicts from movie-events until timeout."""
    for _ in range(timeout_iters):
        msg = consumer.poll(timeout=1.0)
        if msg is None or msg.error():
            continue
        ctx = SerializationContext(msg.topic(), MessageField.VALUE)
        value = deserializer(msg.value(), ctx)
        if value is None:
            continue
        yield value


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

    found = False
    for value in _poll_avro(consumer, deserializer, timeout_iters=90):
        if value.get("user_id") == user_id and value.get("movie_id") == movie_id:
            assert value["event_type"] == "VIEW_STARTED"
            assert value["device_type"] == "MOBILE"
            assert value["event_id"] == event_id
            found = True
            break

    assert found, f"Event for user={user_id} movie={movie_id} not found in Kafka"


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
    for value in _poll_avro(consumer, deserializer, timeout_iters=120):
        if value.get("movie_id") == expected_movie:
            seen_user_ids.add(value.get("user_id"))
            if len(seen_user_ids) >= 5:
                break

    assert len(seen_user_ids) >= 5, f"Only {len(seen_user_ids)}/5 batch events found in Kafka"
