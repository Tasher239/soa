from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from prometheus_client import multiprocess
from prometheus_client import REGISTRY

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
