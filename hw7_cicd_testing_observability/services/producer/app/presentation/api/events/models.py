from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from cinema_shared.schemas.events import MovieEventIn

class PublishResponse(BaseModel):
    event_id: UUID
    published: bool = True


class BatchPublishResult(BaseModel):
    index: int
    event_id: UUID | None
    published: bool
    error: str | None = None


class BatchResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[BatchPublishResult]


class BatchPublishRequest(BaseModel):
    events: list[MovieEventIn] = Field(..., min_length=1, max_length=500)