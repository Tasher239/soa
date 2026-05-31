from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/aggregate", tags=["aggregation"])


@router.post("", summary="Run aggregation for a specific date (idempotent)")
async def trigger_aggregation(
    request: Request,
    target: date = Query(alias="date", description="UTC date to aggregate (YYYY-MM-DD)"),
) -> dict:
    compute = request.app.state.compute_daily
    result = await compute.execute(target, run_type="manual")
    return {
        "target_date": result.target_date.isoformat(),
        "run_type": result.run_type,
        "started_at": result.started_at.isoformat(),
        "finished_at": result.finished_at.isoformat(),
        "rows_processed": result.rows_processed,
        "metrics": [
            {
                "name": str(m.metric_name),
                "value": float(m.metric_value),
                "dimensions": m.dimensions,
            }
            for m in result.metrics
        ],
        "retention": [
            {
                "day_number": c.day_number,
                "cohort_size": c.cohort_size,
                "returned": c.returned,
                "retention_pct": float(c.retention_pct),
            }
            for c in result.retention
        ],
    }
