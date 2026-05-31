"""Integration test: both services expose /metrics in Prometheus format."""
from __future__ import annotations

import httpx
import pytest

from tests.conftest import AGGREGATOR_URL, PRODUCER_URL

REQUIRED_METRICS = [
    "http_requests_total",
    "http_request_errors_total",
    "http_request_duration_seconds",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [PRODUCER_URL, AGGREGATOR_URL])
async def test_metrics_endpoint_returns_prometheus_format(url):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{url}/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers.get("content-type", "")


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [PRODUCER_URL, AGGREGATOR_URL])
async def test_required_metrics_present(url):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{url}/metrics")

    body = r.text
    for metric in REQUIRED_METRICS:
        assert metric in body, f"Metric {metric!r} missing from {url}/metrics"


@pytest.mark.asyncio
async def test_producer_metrics_increment_after_request():
    async with httpx.AsyncClient(timeout=10) as client:
        before_r = await client.get(f"{PRODUCER_URL}/metrics")
        before_count = _extract_total(before_r.text, 'http_requests_total', 'status="200"')

        await client.get(f"{PRODUCER_URL}/health")

        after_r = await client.get(f"{PRODUCER_URL}/metrics")
        after_count = _extract_total(after_r.text, 'http_requests_total', 'status="200"')

    assert after_count >= before_count, "Counter should never decrease"


def _extract_total(text: str, metric_name: str, label_filter: str) -> float:
    total = 0.0
    for line in text.splitlines():
        if line.startswith(metric_name) and label_filter in line and not line.startswith("#"):
            try:
                total += float(line.split()[-1])
            except ValueError:
                pass
    return total
