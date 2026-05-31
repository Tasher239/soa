"""Integration test: Kafka message → ClickHouse events table."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from tests.conftest import PRODUCER_URL, ch_client, unique_id, wait_for_ch_event


@pytest.mark.asyncio
async def test_event_appears_in_clickhouse():
    cid = unique_id()
    user_id = f"ch_test_{cid}"
    movie_id = f"ch_movie_{cid}"

    payload = {
        "user_id": user_id,
        "movie_id": movie_id,
        "event_type": "VIEW_FINISHED",
        "device_type": "TV",
        "session_id": f"sess_{cid}",
        "progress_seconds": 7200,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{PRODUCER_URL}/events", json=payload)
    assert r.status_code == 201, r.text
    event_id = r.json()["event_id"]

    arrived = await wait_for_ch_event(event_id, timeout=45)
    assert arrived, f"event {event_id} did not arrive in ClickHouse"

    async with ch_client() as ch:
        rows = (await ch.query(
            "SELECT user_id, movie_id, event_type, device_type, progress_seconds "
            "FROM cinema.events WHERE event_id = {e:UUID}",
            parameters={"e": event_id},
        )).result_rows

    assert rows, "No row in ClickHouse"
    row_user, row_movie, row_type, row_device, row_progress = rows[0]
    assert row_user == user_id
    assert row_movie == movie_id
    assert str(row_type) == "VIEW_FINISHED"
    assert str(row_device) == "TV"
    assert row_progress == 7200


@pytest.mark.asyncio
async def test_searched_event_stores_search_query():
    cid = unique_id()
    search_q = f"dark knight {cid}"

    payload = {
        "user_id": f"searcher_{cid}",
        "movie_id": "m_search",
        "event_type": "SEARCHED",
        "device_type": "DESKTOP",
        "session_id": f"sess_{cid}",
        "search_query": search_q,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{PRODUCER_URL}/events", json=payload)
    assert r.status_code == 201
    event_id = r.json()["event_id"]

    arrived = await wait_for_ch_event(event_id, timeout=45)
    assert arrived

    async with ch_client() as ch:
        rows = (await ch.query(
            "SELECT search_query FROM cinema.events WHERE event_id = {e:UUID}",
            parameters={"e": event_id},
        )).result_rows

    assert rows and rows[0][0] == search_q


@pytest.mark.asyncio
async def test_clickhouse_rejects_unknown_event_type():
    """Producer validates before Kafka, so unknown event_type returns 422."""
    payload = {
        "user_id": "u1",
        "movie_id": "m1",
        "event_type": "NOT_REAL",
        "device_type": "MOBILE",
        "session_id": "s1",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{PRODUCER_URL}/events", json=payload)
    assert r.status_code == 422
