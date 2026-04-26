from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.infrastructure.database.session import AsyncSessionFactory

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    ch_ok = await request.app.state.clickhouse.ping()

    pg_ok = True
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        pg_ok = False

    healthy = ch_ok and pg_ok
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if healthy else "degraded",
            "clickhouse": "up" if ch_ok else "down",
            "postgres": "up" if pg_ok else "down",
        },
    )


@router.get("/ready")
async def ready() -> dict:
    return {"status": "ready"}
