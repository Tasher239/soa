from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import MetricAggregate, RetentionCohortRow
from app.infrastructure.database.session import get_session

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/{metric_name}")
async def get_metric(
    metric_name: str,
    target: date = Query(alias="date"),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = (
        select(MetricAggregate)
        .where(
            MetricAggregate.metric_date == target,
            MetricAggregate.metric_name == metric_name,
        )
        .order_by(MetricAggregate.id.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "metric_date": r.metric_date.isoformat(),
            "metric_name": r.metric_name,
            "metric_value": float(r.metric_value),
            "dimensions": r.dimensions,
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
        }
        for r in rows
    ]


@router.get("/retention/{cohort_date}")
async def get_retention(
    cohort_date: date,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    stmt = (
        select(RetentionCohortRow)
        .where(RetentionCohortRow.cohort_date == cohort_date)
        .order_by(RetentionCohortRow.day_number.asc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    return [
        {
            "cohort_date": r.cohort_date.isoformat(),
            "day_number": r.day_number,
            "cohort_size": r.cohort_size,
            "returned": r.returned,
            "retention_pct": float(r.retention_pct),
            "computed_at": r.computed_at.isoformat() if r.computed_at else None,
        }
        for r in rows
    ]
