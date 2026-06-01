from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.domain.exceptions import PostgresUnavailable
from app.domain.metrics import MetricPoint, RetentionCohort
from app.infrastructure.database.models import MetricAggregate, RetentionCohortRow


class AggregatesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_metrics(self, metrics: Iterable[MetricPoint]) -> int:
        rows = [
            {
                "metric_date": m.metric_date,
                "metric_name": str(m.metric_name),
                "metric_value": m.metric_value,
                "dimensions": m.dimensions,
            }
            for m in metrics
        ]
        if not rows:
            return 0

        stmt = pg_insert(MetricAggregate).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_metric",
            set_={
                "metric_value": stmt.excluded.metric_value,
                "computed_at": stmt.excluded.computed_at,
            },
        )
        await self._retry(lambda: self._session.execute(stmt))
        return len(rows)

    async def upsert_retention(self, cohorts: Iterable[RetentionCohort]) -> int:
        rows = [
            {
                "cohort_date": c.cohort_date,
                "day_number": c.day_number,
                "cohort_size": c.cohort_size,
                "returned": c.returned,
                "retention_pct": c.retention_pct,
            }
            for c in cohorts
        ]
        if not rows:
            return 0

        stmt = pg_insert(RetentionCohortRow).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["cohort_date", "day_number"],
            set_={
                "cohort_size": stmt.excluded.cohort_size,
                "returned": stmt.excluded.returned,
                "retention_pct": stmt.excluded.retention_pct,
                "computed_at": stmt.excluded.computed_at,
            },
        )
        await self._retry(lambda: self._session.execute(stmt))
        return len(rows)

    async def fetch_metrics_by_date(self, target: date) -> list[MetricAggregate]:
        stmt = select(MetricAggregate).where(MetricAggregate.metric_date == target)
        rows = await self._session.execute(stmt)
        return list(rows.scalars())

    async def fetch_retention_by_date(self, target: date) -> list[RetentionCohortRow]:
        stmt = select(RetentionCohortRow).where(RetentionCohortRow.cohort_date == target)
        rows = await self._session.execute(stmt)
        return list(rows.scalars())

    async def _retry(self, func):
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.retry_attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=settings.retry_min_seconds,
                    max=settings.retry_max_seconds,
                ),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    await func()
        except Exception as exc:
            raise PostgresUnavailable(str(exc)) from exc
