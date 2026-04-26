from __future__ import annotations

import asyncio

import pytest
import pytest_asyncio

from tests.helpers import AGGREGATOR_URL, PRODUCER_URL, wait_http_200
import httpx

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def wait_services_ready() -> None:
    await asyncio.gather(
        wait_http_200(f"{PRODUCER_URL}/health"),
        wait_http_200(f"{AGGREGATOR_URL}/health"),
    )


@pytest_asyncio.fixture(scope="session", autouse=True)
async def stop_generator_for_tests(wait_services_ready) -> None:


    async with httpx.AsyncClient(timeout=5) as client:
        try:
            await client.post(f"{PRODUCER_URL}/generator/stop")
        except Exception:
            pass
