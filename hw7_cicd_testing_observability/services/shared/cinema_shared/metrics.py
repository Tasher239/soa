from __future__ import annotations

import time

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
    REGISTRY,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response as StarletteResponse

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
)
http_request_errors_total = Counter(
    "http_request_errors_total",
    "Total HTTP request errors",
    ["method", "endpoint", "error_type"],
)
http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
kafka_messages_consumed_total = Counter(
    "kafka_messages_consumed_total",
    "Kafka messages consumed",
    ["topic", "status"],
)
kafka_consumer_lag = Gauge(
    "kafka_consumer_lag",
    "Kafka consumer lag",
    ["topic", "group", "partition"],
)
event_processing_delay_seconds = Histogram(
    "event_processing_delay_seconds",
    "Time from event.timestamp to consumer processing (seconds)",
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> StarletteResponse:
        method = request.method
        route = request.scope.get("route")
        endpoint = route.path if route else request.url.path

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration = time.perf_counter() - start
            status = str(response.status_code)
            http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
            return response
        except Exception as exc:
            duration = time.perf_counter() - start
            error_type = type(exc).__name__
            http_request_errors_total.labels(
                method=method, endpoint=endpoint, error_type=error_type
            ).inc()
            http_requests_total.labels(method=method, endpoint=endpoint, status="500").inc()
            http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
            raise


def build_metrics_router(registry: CollectorRegistry | None = None) -> APIRouter:
    router = APIRouter()
    reg = registry

    @router.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        active_reg = reg
        if active_reg is None:
            active_reg = CollectorRegistry()
            try:
                multiprocess.MultiProcessCollector(active_reg)
            except (ValueError, KeyError):
                active_reg = REGISTRY
        return Response(generate_latest(active_reg), media_type=CONTENT_TYPE_LATEST)

    return router
