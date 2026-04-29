from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

import clickhouse_connect
import httpx


def env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if v is None:
        raise RuntimeError(f"Missing env var {name}")
    return v


PRODUCER_URL = env("PRODUCER_URL")
AGGREGATOR_URL = env("AGGREGATOR_URL")
CLICKHOUSE_URL = env("CLICKHOUSE_URL")
POSTGRES_DSN = env("POSTGRES_DSN")
S3_ENDPOINT = env("S3_ENDPOINT")
S3_BUCKET = env("S3_BUCKET")
S3_ACCESS_KEY = env("S3_ACCESS_KEY")
S3_SECRET_KEY = env("S3_SECRET_KEY")


def unique_suffix() -> str:
    return uuid.uuid4().hex[:12]


async def wait_http_200(url: str, timeout: float = 120.0, interval: float = 2.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    async with httpx.AsyncClient(timeout=5) as client:
        last_exc: Exception | None = None
        while asyncio.get_event_loop().time() < deadline:
            try:
                r = await client.get(url)
                if r.status_code == 200:
                    return
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
            await asyncio.sleep(interval)
        raise RuntimeError(f"Timeout waiting for {url}: {last_exc}")


@asynccontextmanager
async def ch_client():
    client = await clickhouse_connect.get_async_client(
        interface="http",
        host=CLICKHOUSE_URL.replace("http://", "").split(":")[0],
        port=int(CLICKHOUSE_URL.rsplit(":", 1)[-1]),
        database="cinema",
    )
    try:
        yield client
    finally:
        await client.close()


async def count_events_by_event_id(event_id: str) -> int:
    async with ch_client() as ch:
        rows = (
            await ch.query(
                "SELECT count() FROM cinema.events WHERE event_id = {e:UUID}",
                parameters={"e": event_id},
            )
        ).result_rows
        return int(rows[0][0]) if rows else 0


async def wait_for_event(event_id: str, timeout: float = 45.0, interval: float = 0.5) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if await count_events_by_event_id(event_id) > 0:
            return True
        await asyncio.sleep(interval)
    return False
