from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_session
from app.infrastructure.repositories.runs_repo import RunsRepository

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
async def list_runs(
    limit: int = Query(20, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    repo = RunsRepository(session)
    runs = await repo.list_recent(limit=limit)
    return [
        {
            "id": r.id,
            "run_type": r.run_type,
            "target_date": r.target_date.isoformat(),
            "started_at": r.started_at.isoformat(),
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "status": r.status,
            "rows_processed": r.rows_processed,
            "error": r.error,
        }
        for r in runs
    ]
