from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import pytest

from tests.helpers import PRODUCER_URL, ch_client, unique_suffix, wait_for_event


@pytest.mark.asyncio
async def test_single_event_end_to_end():
    event_id = str(uuid.uuid4())
    user_id = f"test_user_{unique_suffix()}"
    movie_id = f"test_movie_{unique_suffix()}"
    session_id = f"test_session_{unique_suffix()}"

    payload = {
        "event_id": event_id,
        "user_id": user_id,
        "movie_id": movie_id,
        "event_type": "VIEW_STARTED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "device_type": "MOBILE",
        "session_id": session_id,
        "progress_seconds": 0,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{PRODUCER_URL}/events", json=payload)
    assert r.status_code == 201, r.text
    assert r.json()["event_id"] == event_id
    assert r.json()["published"] is True

    arrived = await wait_for_event(event_id, timeout=45)
    assert arrived, f"event {event_id} did not arrive in ClickHouse in time"

    async with ch_client() as ch:
        rows = (
            await ch.query(
                "SELECT user_id, movie_id, event_type, session_id, device_type "
                "FROM cinema.events WHERE event_id = {e:UUID}",
                parameters={"e": event_id},
            )
        ).result_rows

    assert rows, "no row returned"
    r_user, r_movie, r_type, r_session, r_device = rows[0]
    assert r_user == user_id
    assert r_movie == movie_id
    assert str(r_type) == "VIEW_STARTED"
    assert r_session == session_id
    assert str(r_device) == "MOBILE"


@pytest.mark.asyncio
async def test_batch_publish_end_to_end():
    batch_tag = unique_suffix()
    events = []
    for i in range(25):
        events.append({
            "user_id": f"batch_user_{batch_tag}_{i:03d}",
            "movie_id": f"m_{batch_tag}",
            "event_type": "LIKED",
            "device_type": "DESKTOP",
            "session_id": f"sess_{batch_tag}_{i}",
        })

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{PRODUCER_URL}/events/batch", json={"events": events})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == len(events)
    assert body["succeeded"] == len(events), f"failures: {body}"

    import asyncio
    async with ch_client() as ch:
        for _ in range(60):
            rows = (
                await ch.query(
                    "SELECT count() FROM cinema.events WHERE movie_id = {m:String}",
                    parameters={"m": f"m_{batch_tag}"},
                )
            ).result_rows
            if rows and int(rows[0][0]) >= len(events):
                break
            await asyncio.sleep(0.5)
        assert int(rows[0][0]) >= len(events), f"only {rows[0][0]} events reached CH"


@pytest.mark.asyncio
async def test_validation_rejects_bad_event():
    bad = {"user_id": "", "movie_id": "m1", "event_type": "NOT_A_TYPE", "device_type": "MOBILE", "session_id": "s1"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(f"{PRODUCER_URL}/events", json=bad)
    assert r.status_code == 422
