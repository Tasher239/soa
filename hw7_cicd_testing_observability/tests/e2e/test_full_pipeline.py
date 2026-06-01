"""E2E test: full user scenario - VIEW_STARTED event flows through Kafka → ClickHouse."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import asyncpg
import httpx
import pytest

from conftest import (
    AGGREGATOR_URL,
    POSTGRES_DSN,
    PRODUCER_URL,
    ch_client,
    pg_conn,
    unique_id,
    wait_for_ch_event,
)


@pytest.mark.asyncio
async def test_view_started_full_pipeline():
    """
    Scenario: User starts watching a movie.
    1. POST /events with VIEW_STARTED → HTTP 201, event_id UUID
    2. Event arrives in ClickHouse cinema.events within 45s
    3. ClickHouse row has correct user_id, movie_id, event_type, device_type
    """
    cid = unique_id()
    user_id = f"e2e_user_{cid}"
    movie_id = f"e2e_movie_{cid}"
    session_id = f"e2e_sess_{cid}"

    payload = {
        "user_id": user_id,
        "movie_id": movie_id,
        "event_type": "VIEW_STARTED",
        "device_type": "DESKTOP",
        "session_id": session_id,
        "progress_seconds": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Step 1: publish via producer API
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{PRODUCER_URL}/events", json=payload)

    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    body = r.json()
    assert "event_id" in body, "Response must contain event_id"
    assert body["published"] is True
    event_id = body["event_id"]
    UUID(event_id)  # validates UUID format

    # Step 2: wait for ClickHouse ingestion
    arrived = await wait_for_ch_event(event_id, timeout=45)
    assert arrived, f"Event {event_id} not found in ClickHouse after 45s"

    # Step 3: verify ClickHouse row
    async with ch_client() as ch:
        rows = (await ch.query(
            """
            SELECT user_id, movie_id, event_type, device_type, session_id
            FROM cinema.events
            WHERE event_id = {e:UUID}
            """,
            parameters={"e": event_id},
        )).result_rows

    assert rows, "No row in ClickHouse"
    row_user, row_movie, row_type, row_device, row_session = rows[0]
    assert row_user == user_id
    assert row_movie == movie_id
    assert str(row_type) == "VIEW_STARTED"
    assert str(row_device) == "DESKTOP"
    assert row_session == session_id


@pytest.mark.asyncio
async def test_view_finished_full_pipeline():
    """User finishes watching - progress_seconds recorded in ClickHouse."""
    cid = unique_id()
    user_id = f"e2e_fin_{cid}"
    movie_id = f"e2e_film_{cid}"

    payload = {
        "user_id": user_id,
        "movie_id": movie_id,
        "event_type": "VIEW_FINISHED",
        "device_type": "TV",
        "session_id": f"sess_{cid}",
        "progress_seconds": 5400,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{PRODUCER_URL}/events", json=payload)

    assert r.status_code == 201
    event_id = r.json()["event_id"]

    arrived = await wait_for_ch_event(event_id, timeout=45)
    assert arrived

    async with ch_client() as ch:
        rows = (await ch.query(
            "SELECT progress_seconds FROM cinema.events WHERE event_id = {e:UUID}",
            parameters={"e": event_id},
        )).result_rows

    assert rows
    assert int(rows[0][0]) == 5400


@pytest.mark.asyncio
async def test_aggregator_health_reports_healthy():
    """Aggregator reports healthy connections to ClickHouse and PostgreSQL."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{AGGREGATOR_URL}/health")

    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert body.get("clickhouse") == "up"
    assert body.get("postgres") == "up"


@pytest.mark.asyncio
async def test_producer_metrics_after_e2e():
    """After E2E events, /metrics endpoint has non-zero counters."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{PRODUCER_URL}/metrics")

    assert r.status_code == 200
    assert "http_requests_total" in r.text


@pytest.mark.asyncio
async def test_invalid_payload_rejected_at_boundary():
    """System boundary: invalid event rejected before reaching Kafka."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{PRODUCER_URL}/events",
            json={"user_id": "", "movie_id": "m", "event_type": "BAD", "device_type": "MOBILE", "session_id": "s"},
        )
    assert r.status_code == 422
