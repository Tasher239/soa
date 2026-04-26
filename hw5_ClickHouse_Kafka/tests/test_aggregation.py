from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from uuid import uuid4

import asyncpg
import httpx
import pytest

from tests.helpers import (
    AGGREGATOR_URL,
    POSTGRES_DSN,
    PRODUCER_URL,
    ch_client,
    unique_suffix,
)


async def _seed_events(total_users: int = 5, movie_views: int = 3) -> str:
    tag = unique_suffix()
    now = datetime.now(timezone.utc)

    async with httpx.AsyncClient(timeout=30) as client:
        for u in range(total_users):
            for v in range(movie_views):
                await client.post(
                    f"{PRODUCER_URL}/events",
                    json={
                        "user_id": f"agg_user_{tag}_{u}",
                        "movie_id": f"agg_movie_{tag}_{v}",
                        "event_type": "VIEW_STARTED",
                        "device_type": "MOBILE" if v % 2 == 0 else "DESKTOP",
                        "session_id": f"agg_sess_{tag}_{u}_{v}",
                        "progress_seconds": 0,
                        "timestamp": now.isoformat(),
                    },
                )
                if v < 2:
                    await client.post(
                        f"{PRODUCER_URL}/events",
                        json={
                            "user_id": f"agg_user_{tag}_{u}",
                            "movie_id": f"agg_movie_{tag}_{v}",
                            "event_type": "VIEW_FINISHED",
                            "device_type": "MOBILE" if v % 2 == 0 else "DESKTOP",
                            "session_id": f"agg_sess_{tag}_{u}_{v}",
                            "progress_seconds": 3600,
                            "timestamp": now.isoformat(),
                        },
                    )

    await asyncio.sleep(3)
    async with ch_client() as ch:
        for _ in range(60):
            rows = (
                await ch.query(
                    "SELECT count() FROM cinema.events WHERE user_id LIKE {p:String}",
                    parameters={"p": f"agg_user_{tag}_%"},
                )
            ).result_rows
            if rows and int(rows[0][0]) >= total_users * (movie_views + 2):
                break
            await asyncio.sleep(0.5)
    return tag


@pytest.mark.asyncio
async def test_aggregate_today_idempotent():
    await _seed_events()
    target = date.today().isoformat()

    async with httpx.AsyncClient(timeout=60) as client:
        r1 = await client.post(f"{AGGREGATOR_URL}/aggregate?date={target}")
        assert r1.status_code == 200, r1.text
        body1 = r1.json()
        assert body1["target_date"] == target
        assert body1["rows_processed"] > 0

        r2 = await client.post(f"{AGGREGATOR_URL}/aggregate?date={target}")
        assert r2.status_code == 200, r2.text

    conn = await asyncpg.connect(dsn=POSTGRES_DSN)
    try:
        dau_rows = await conn.fetch(
            "SELECT count(*) FROM metric_aggregates "
            "WHERE metric_date = $1 AND metric_name = 'dau'",
            date.today(),
        )
        assert dau_rows[0]["count"] == 1, "DAU must be a single row per date (idempotent)"

        retention_count = await conn.fetchval(
            "SELECT count(*) FROM retention_cohorts WHERE cohort_date = $1",
            date.today(),
        )
        assert retention_count <= 8

        names = await conn.fetch(
            "SELECT DISTINCT metric_name FROM metric_aggregates WHERE metric_date = $1",
            date.today(),
        )
        present = {r["metric_name"] for r in names}
        assert {"dau", "avg_watch_seconds", "conversion"}.issubset(present)
    finally:
        await conn.close()
