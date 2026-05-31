from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class MetricName(StrEnum):
    DAU = "dau"
    AVG_WATCH_SECONDS = "avg_watch_seconds"
    CONVERSION = "conversion"
    TOP_MOVIE_VIEWS = "top_movie_views"
    DEVICE_EVENTS = "device_events"
    DEVICE_USERS = "device_users"


@dataclass(slots=True)
class MetricPoint:
    metric_date: date
    metric_name: MetricName
    metric_value: Decimal
    dimensions: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetentionCohort:
    cohort_date: date
    day_number: int
    cohort_size: int
    returned: int
    retention_pct: Decimal


@dataclass(slots=True)
class AggregationResult:
    run_type: str
    target_date: date
    started_at: datetime
    finished_at: datetime
    metrics: list[MetricPoint]
    retention: list[RetentionCohort]

    @property
    def rows_processed(self) -> int:
        return len(self.metrics) + len(self.retention)
