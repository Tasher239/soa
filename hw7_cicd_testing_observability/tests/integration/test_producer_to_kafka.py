"""Integration test: POST /events → message arrives in Kafka topic."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import pytest
from confluent_kafka import Consumer, KafkaException

from tests.conftest import KAFKA_BOOTSTRAP_SERVERS, PRODUCER_URL, unique_id


@pytest.fixture
def kafka_consumer():
    group_id = f"test-{unique_id()}"
    c = Consumer({
        "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    c.subscribe(["movie-events"])
    yield c
    c.close()


@pytest.mark.asyncio
async def test_published_event_reaches_kafka(kafka_consumer):
    correlation_id = unique_id()
    user_id = f"integ_user_{correlation_id}"
    payload = {
        "user_id": user_id,
        "movie_id": f"movie_{correlation_id}",
        "event_type": "VIEW_STARTED",
        "device_type": "MOBILE",
        "session_id": f"sess_{correlation_id}",
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{PRODUCER_URL}/events", json=payload)
    assert r.status_code == 201, r.text
    event_id = r.json()["event_id"]
    assert uuid.UUID(event_id)

    found = False
    for _ in range(60):
        msg = kafka_consumer.poll(timeout=1.0)
        if msg is None:
            continue
        if msg.error():
            continue
        value = msg.value()
        if value and correlation_id.encode() in value:
            found = True
            break

    assert found, f"Event with correlation_id={correlation_id} not found in Kafka after 60s"


@pytest.mark.asyncio
async def test_batch_publish_all_reach_kafka(kafka_consumer):
    tag = unique_id()
    events = [
        {
            "user_id": f"batch_{tag}_{i}",
            "movie_id": f"m_{tag}",
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

    found_count = 0
    for _ in range(120):
        msg = kafka_consumer.poll(timeout=0.5)
        if msg and not msg.error() and msg.value():
            if f"m_{tag}".encode() in msg.value():
                found_count += 1
            if found_count >= 5:
                break

    assert found_count >= 5, f"Only {found_count}/5 batch events found in Kafka"
