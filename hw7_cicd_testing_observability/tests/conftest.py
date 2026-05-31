from __future__ import annotations

import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import asyncpg
import clickhouse_connect
import httpx
import pytest


PRODUCER_URL = os.environ.get("PRODUCER_URL", "http://localhost:8000")
AGGREGATOR_URL = os.environ.get("AGGREGATOR_URL", "http://localhost:8001")
CLICKHOUSE_HOST = os.environ.get("CLICKHOUSE_HOST", "localhost")
CLICKHOUSE_PORT = int(os.environ.get("CLICKHOUSE_PORT", "8123"))
POSTGRES_DSN = os.environ.get("POSTGRES_DSN", "postgresql://cinema:cinema@localhost:5433/cinema")
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
SCHEMA_REGISTRY_URL = os.environ.get("SCHEMA_REGISTRY_URL", "http://localhost:8081")


def unique_id() -> str:
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
            except Exception as exc:
                last_exc = exc
            await asyncio.sleep(interval)
    raise RuntimeError(f"Timeout waiting for {url}: {last_exc}")


@asynccontextmanager
async def ch_client():
    client = await clickhouse_connect.get_async_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database="cinema",
    )
    try:
        yield client
    finally:
        await client.close()


@asynccontextmanager
async def pg_conn():
    conn = await asyncpg.connect(POSTGRES_DSN)
    try:
        yield conn
    finally:
        await conn.close()


async def wait_for_ch_event(event_id: str, timeout: float = 45.0) -> bool:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        async with ch_client() as ch:
            rows = (await ch.query(
                "SELECT count() FROM cinema.events WHERE event_id = {e:UUID}",
                parameters={"e": event_id},
            )).result_rows
            if rows and int(rows[0][0]) > 0:
                return True
        await asyncio.sleep(0.5)
    return False


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def wait_services():
    await asyncio.gather(
        wait_http_200(f"{PRODUCER_URL}/health"),
        wait_http_200(f"{AGGREGATOR_URL}/health"),
    )


@pytest.fixture(scope="session", autouse=True)
async def disable_generator(wait_services):
    async with httpx.AsyncClient(timeout=5) as client:
        try:
            await client.post(f"{PRODUCER_URL}/generator/stop")
        except Exception:
            pass
