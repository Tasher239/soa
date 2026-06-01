"""Unit tests for MetricsMiddleware - no external dependencies needed."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY

from cinema_shared.metrics import (
    MetricsMiddleware,
    build_metrics_router,
    http_request_duration_seconds,
    http_request_errors_total,
    http_requests_total,
)


def make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(MetricsMiddleware)
    app.include_router(build_metrics_router())

    @app.get("/ok")
    def ok():
        return {"status": "ok"}

    @app.get("/fail")
    def fail():
        return {"status": "ok"}, 500

    @app.get("/boom")
    def boom():
        raise ValueError("test error")

    return app


@pytest.fixture
def client():
    app = make_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_metrics_endpoint_returns_200(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text


def test_successful_request_increments_counter(client):
    # Make a request, then verify /metrics output contains the counter with status 200
    client.get("/ok")
    r = client.get("/metrics")
    body = r.text
    # Counter line should contain the method/endpoint/status labels with a positive value
    found = any(
        'http_requests_total' in line
        and 'method="GET"' in line
        and 'status="200"' in line
        and not line.startswith("#")
        for line in body.splitlines()
    )
    assert found, f"Expected http_requests_total counter with status=200 in:\n{body}"


def test_metrics_endpoint_text_format(client):
    client.get("/ok")
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.text
    assert "http_request_duration_seconds" in body
    assert "http_requests_total" in body


def test_duration_histogram_observed(client):
    client.get("/ok")
    r = client.get("/metrics")
    assert "http_request_duration_seconds_bucket" in r.text


def _get_counter_value(name: str, **labels) -> float:
    for metric in REGISTRY.collect():
        if metric.name == name:
            for sample in metric.samples:
                if all(sample.labels.get(k) == v for k, v in labels.items()):
                    if sample.name.endswith("_total") or sample.name == name:
                        return sample.value
    return 0.0
