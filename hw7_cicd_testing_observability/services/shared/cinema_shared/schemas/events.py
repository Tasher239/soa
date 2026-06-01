from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from cinema_shared.schemas.constants import DeviceType, EventType


class MovieEventIn(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    event_id: UUID | None = None
    user_id: str = Field(min_length=1, max_length=128)
    movie_id: str = Field(min_length=1, max_length=128)
    event_type: EventType
    timestamp: datetime | None = None
    device_type: DeviceType
    session_id: str = Field(min_length=1, max_length=128)
    progress_seconds: int | None = Field(default=None, ge=0, le=86400)
    search_query: str | None = Field(default=None, max_length=512)
    client_version: str | None = Field(default=None, max_length=64)

    @field_validator("timestamp")
    @classmethod
    def ensure_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    def materialize(self) -> MovieEvent:
        return MovieEvent(
            event_id=self.event_id or uuid4(),
            user_id=self.user_id,
            movie_id=self.movie_id,
            event_type=EventType(self.event_type),
            timestamp=self.timestamp or datetime.now(timezone.utc),
            device_type=DeviceType(self.device_type),
            session_id=self.session_id,
            progress_seconds=self.progress_seconds,
            search_query=self.search_query,
            client_version=self.client_version,
        )


class MovieEvent(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    event_id: UUID
    user_id: str
    movie_id: str
    event_type: EventType
    timestamp: datetime
    device_type: DeviceType
    session_id: str
    progress_seconds: int | None = None
    search_query: str | None = None
    client_version: str | None = None

    def to_avro_dict(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "user_id": self.user_id,
            "movie_id": self.movie_id,
            "event_type": str(self.event_type),
            "timestamp": self.timestamp,
            "device_type": str(self.device_type),
            "session_id": self.session_id,
            "progress_seconds": self.progress_seconds,
            "search_query": self.search_query,
            "client_version": self.client_version,
        }

    def log_fields(self) -> dict[str, Any]:
        return {
            "event_id": str(self.event_id),
            "event_type": str(self.event_type),
            "user_id": self.user_id,
            "movie_id": self.movie_id,
            "timestamp": self.timestamp.isoformat(),
        }
