from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Index, Numeric, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.database.base import Base


class MetricAggregate(Base):
    __tablename__ = "metric_aggregates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    metric_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    metric_value: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    dimensions: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="'{}'::jsonb")
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("metric_date", "metric_name", "dimensions", name="uq_metric"),
    )


class RetentionCohortRow(Base):
    __tablename__ = "retention_cohorts"

    cohort_date: Mapped[date] = mapped_column(Date, primary_key=True)
    day_number: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    cohort_size: Mapped[int] = mapped_column(nullable=False)
    returned: Mapped[int] = mapped_column(nullable=False)
    retention_pct: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AggregationRun(Base):
    __tablename__ = "aggregation_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    rows_processed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
