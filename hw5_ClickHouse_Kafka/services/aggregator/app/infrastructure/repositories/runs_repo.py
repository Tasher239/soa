from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models import AggregationRun


class RunsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start_run(self, run_type: str, target: date) -> AggregationRun:
        row = AggregationRun(
            run_type=run_type,
            target_date=target,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def finish_run(
        self,
        run_id: int,
        rows_processed: int,
        status: str = "success",
        error: str | None = None,
    ) -> None:
        row = await self._session.get(AggregationRun, run_id)
        if row is None:
            return
        row.finished_at = datetime.now(timezone.utc)
        row.rows_processed = rows_processed
        row.status = status
        row.error = error
        await self._session.flush()

    async def list_recent(self, limit: int = 20) -> list[AggregationRun]:
        stmt = select(AggregationRun).order_by(AggregationRun.id.desc()).limit(limit)
        rows = await self._session.execute(stmt)
        return list(rows.scalars())
