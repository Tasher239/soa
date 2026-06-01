from __future__ import annotations

from fastapi import APIRouter, Query, Request, status

router = APIRouter()


@router.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def start_generator(
    request: Request,
    rps: int = Query(default=None, ge=1, le=10000, description="Target aggregate events/sec"),
    users: int = Query(default=None, ge=1, le=2000, description="Concurrent simulated users"),
) -> dict:
    sim = request.app.state.simulator
    await sim.start(rps=rps, users=users)
    return {"started": True, **sim.status}


@router.post("/stop", status_code=status.HTTP_202_ACCEPTED)
async def stop_generator(request: Request) -> dict:
    sim = request.app.state.simulator
    await sim.stop()
    return {"stopped": True, **sim.status}


@router.get("/status")
async def generator_status(request: Request) -> dict:
    return request.app.state.simulator.status
