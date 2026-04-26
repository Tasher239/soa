from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from cinema_shared.schemas.events import MovieEventIn

from app.presentation.api.events.models import PublishResponse, BatchResponse, BatchPublishRequest, BatchPublishResult

router = APIRouter()


@router.post("", response_model=PublishResponse, status_code=status.HTTP_201_CREATED)
async def publish_event(event: MovieEventIn, request: Request) -> PublishResponse:
    use_case = request.app.state.publish_event
    try:
        event_id = await use_case(event)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Publish failed: {exc}") from exc
    return PublishResponse(event_id=event_id)


@router.post("/batch", response_model=BatchResponse)
async def publish_batch(body: BatchPublishRequest, request: Request) -> BatchResponse:
    use_case = request.app.state.publish_event

    async def _one(idx: int, evt: MovieEventIn) -> BatchPublishResult:
        try:
            eid = await use_case(evt)
            return BatchPublishResult(index=idx, event_id=eid, published=True)
        except Exception as exc:
            return BatchPublishResult(index=idx, event_id=None, published=False, error=str(exc))

    results: list[Any] = await asyncio.gather(
        *[_one(i, e) for i, e in enumerate(body.events)],
        return_exceptions=False,
    )
    succeeded = sum(1 for r in results if r.published)
    return BatchResponse(
        total=len(results),
        succeeded=succeeded,
        failed=len(results) - succeeded,
        results=results,
    )
