from __future__ import annotations

import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from cinema_shared.logging import configure_logging, get_logger
from cinema_shared.metrics import MetricsMiddleware, build_metrics_router, event_processing_delay_seconds
from cinema_shared.request_id import RequestIdMiddleware

from app.application.compute_daily import ComputeDailyAggregates
from app.application.s3_export import ExportDailyAggregates
from app.application.scheduler import AggregationScheduler
from app.core.config import settings
from app.domain.exceptions import AggregatorError
from app.infrastructure.clickhouse_client import ClickHouseGateway
from app.infrastructure.database.session import dispose_engine
from app.presentation.error_handlers import (
    aggregator_error_handler,
    validation_error_handler,
)
from app.presentation.routers import aggregate, export, health, metrics_api, runs

log = get_logger("aggregator.main")


async def _measure_processing_delay(ch: ClickHouseGateway) -> None:
    """
    Periodically samples recent ClickHouse events and measures the delay
    between the event's own timestamp and the time it was observed in CH.
    This represents the Kafka→ClickHouse ingestion latency (SLI 3).
    """
    while True:
        await asyncio.sleep(30)
        try:
            rows = await ch.query(
                """
                SELECT toUnixTimestamp64Micro(timestamp) AS ts_us
                FROM cinema.events
                WHERE timestamp >= now() - INTERVAL 2 MINUTE
                ORDER BY timestamp DESC
                LIMIT 100
                """
            )
            now_us = time.time() * 1_000_000
            for (ts_us,) in rows:
                delay_s = (now_us - float(ts_us)) / 1_000_000
                if 0 <= delay_s < 3600:
                    event_processing_delay_seconds.observe(delay_s)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)

    ch = ClickHouseGateway()
    await ch.connect()

    compute = ComputeDailyAggregates(ch)
    exporter = ExportDailyAggregates()
    scheduler = AggregationScheduler(compute, exporter)
    scheduler.start()

    delay_task = asyncio.create_task(_measure_processing_delay(ch))

    app.state.clickhouse = ch
    app.state.compute_daily = compute
    app.state.s3_export = exporter
    app.state.scheduler = scheduler

    log.info("aggregator_ready")

    try:
        yield
    finally:
        log.info("aggregator_shutting_down")
        delay_task.cancel()
        scheduler.shutdown()
        await ch.close()
        await dispose_engine()
        log.info("aggregator_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cinema Aggregation Service",
        version="1.0.0",
        description=(
            "Computes daily analytics (DAU, watch time, conversion, top movies, "
            "device distribution, D0–D7 retention cohorts) from ClickHouse, "
            "writes to PostgreSQL, exports daily aggregates to S3."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(MetricsMiddleware)
    app.add_middleware(RequestIdMiddleware)

    app.add_exception_handler(AggregatorError, aggregator_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    app.include_router(health.router)
    app.include_router(aggregate.router)
    app.include_router(export.router)
    app.include_router(metrics_api.router)
    app.include_router(runs.router)
    app.include_router(build_metrics_router())

    return app


app = create_app()
