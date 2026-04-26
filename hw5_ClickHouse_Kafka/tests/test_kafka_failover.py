from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import docker
import httpx
import pytest

from tests.helpers import PRODUCER_URL, unique_suffix, wait_for_event


def _kafka2_container():
    client = docker.from_env()
    for name in ("cinema_kafka_2", "cinema-kafka-2"):
        try:
            return client.containers.get(name)
        except Exception:
            continue
    for c in client.containers.list(all=True):
        if "kafka-2" in c.name:
            return c
    return None


async def _publish_event(tag: str, idx: int) -> str:
    event_id = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{PRODUCER_URL}/events",
            json={
                "event_id": event_id,
                "user_id": f"failover_user_{tag}_{idx}",
                "movie_id": f"m_failover_{tag}",
                "event_type": "VIEW_STARTED",
                "device_type": "TV",
                "session_id": f"sess_failover_{tag}_{idx}",
                "progress_seconds": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert r.status_code == 201, r.text
    return event_id


@pytest.mark.asyncio
async def test_kafka_broker_failover():
    tag = unique_suffix()

    baseline_id = await _publish_event(tag, 0)
    assert await wait_for_event(baseline_id, timeout=45)

    ktwo = _kafka2_container()
    if ktwo is None:
        pytest.skip("Cannot find kafka-2 container from test runner (docker socket unavailable)")

    ktwo.pause()
    try:
        await asyncio.sleep(5)

        written_ids = []
        for i in range(1, 6):
            eid = await _publish_event(tag, i)
            written_ids.append(eid)

        arrived = 0
        for eid in written_ids:
            if await wait_for_event(eid, timeout=60):
                arrived += 1
        assert arrived == len(written_ids), f"only {arrived}/{len(written_ids)} events arrived with kafka-2 paused"
    finally:
        ktwo.unpause()
        await asyncio.sleep(3)

    post_id = await _publish_event(tag, 99)
    assert await wait_for_event(post_id, timeout=60)
