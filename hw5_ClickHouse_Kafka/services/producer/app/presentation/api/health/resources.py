from __future__ import annotations

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    producer = request.app.state.kafka_producer
    healthy = await producer.healthy()
    status_code = status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if healthy else "degraded",
            "kafka": "up" if healthy else "down",
            "generator": request.app.state.simulator.status,
        },
    )


@router.get("/ready")
async def ready() -> dict:
    return {"status": "ready"}
