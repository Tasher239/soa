from __future__ import annotations

import asyncio
import time
from datetime import date, datetime, timezone

from prometheus_client import Counter, Histogram
from sqlalchemy.ext.asyncio import AsyncSession

from cinema_shared.logging import get_logger

from app.application.metrics import (
    compute_avg_watch_time,
    compute_conversion,
    compute_dau,
    compute_device_distribution,
    compute_retention,
    compute_top_movies,
)
from app.core.config import settings
from app.domain.metrics import AggregationResult, MetricPoint, RetentionCohort
from app.infrastructure.clickhouse_client import ClickHouseGateway
from app.infrastructure.database.session import AsyncSessionFactory
from app.infrastructure.repositories.aggregates_repo import AggregatesRepository
from app.infrastructure.repositories.runs_repo import RunsRepository

logger = get_logger("aggregator.compute")

AGG_RUNS = Counter(
    "cinema_aggregation_runs_total",
    "Total aggregation runs",
    ["run_type", "status"],
)
AGG_DURATION = Histogram(
    "cinema_aggregation_duration_seconds",
    "Wall-clock duration of one aggregation run",
    buckets=(0.5, 1, 2, 5, 10, 30, 60, 120, 300),
)


class ComputeDailyAggregates:
    def __init__(self, ch: ClickHouseGateway) -> None:
        self._ch = ch

    async def execute(self, target: date, run_type: str = "manual") -> AggregationResult:
        started_at = datetime.now(timezone.utc)
        t0 = time.perf_counter()

        logger.info("aggregation_started", target=str(target), run_type=run_type)

        session: AsyncSession
        async with AsyncSessionFactory() as session:
            runs_repo = RunsRepository(session)
            agg_repo = AggregatesRepository(session)

            run = await runs_repo.start_run(run_type, target)
            await session.commit()

            run_id = run.id
            try:
                (
                    dau,
                    avg_watch,
                    conversion,
                    top_movies,
                    device_dist,
                    retention,
                ) = await asyncio.gather(
                    compute_dau(self._ch, target),
                    compute_avg_watch_time(self._ch, target),
                    compute_conversion(self._ch, target),
                    compute_top_movies(self._ch, target, limit=10),
                    compute_device_distribution(self._ch, target),
                    compute_retention(self._ch, target, settings.retention_window_days),
                )

                metrics: list[MetricPoint] = [dau, avg_watch, conversion, *top_movies, *device_dist]
                cohorts: list[RetentionCohort] = retention

                written = await agg_repo.upsert_metrics(metrics)
                written += await agg_repo.upsert_retention(cohorts)
                await session.commit()

                duration_s = time.perf_counter() - t0
                AGG_DURATION.observe(duration_s)
                AGG_RUNS.labels(run_type, "success").inc()

                await runs_repo.finish_run(run_id, rows_processed=written, status="success")
                await session.commit()

                finished_at = datetime.now(timezone.utc)
                logger.info(
                    "aggregation_finished",
                    target=str(target),
                    run_type=run_type,
                    rows_processed=written,
                    duration_ms=round(duration_s * 1000, 2),
                    dau=float(dau.metric_value),
                    conversion=float(conversion.metric_value),
                    avg_watch_seconds=float(avg_watch.metric_value),
                )
                return AggregationResult(
                    run_type=run_type,
                    target_date=target,
                    started_at=started_at,
                    finished_at=finished_at,
                    metrics=metrics,
                    retention=cohorts,
                )
            except Exception as exc:
                AGG_RUNS.labels(run_type, "failed").inc()
                try:
                    await runs_repo.finish_run(
                        run_id,
                        rows_processed=0,
                        status="failed",
                        error=str(exc)[:2000],
                    )
                    await session.commit()
                except Exception:
                    await session.rollback()
                logger.exception("aggregation_failed", target=str(target), run_type=run_type)
                raise
