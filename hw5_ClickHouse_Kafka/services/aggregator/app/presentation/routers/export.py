from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/export", tags=["export"])


@router.post("", summary="Export aggregates for a date to S3 (overwrite)")
async def trigger_export(
    request: Request,
    target: date = Query(alias="date"),
) -> dict:
    exporter = request.app.state.s3_export
    return await exporter.execute(target)
