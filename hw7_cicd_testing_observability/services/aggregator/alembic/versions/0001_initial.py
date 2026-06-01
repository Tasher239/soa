"""initial schema: metric_aggregates, retention_cohorts, aggregation_runs

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-23
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "metric_aggregates",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("metric_date", sa.Date, nullable=False),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("metric_value", sa.Numeric(20, 6), nullable=False),
        sa.Column(
            "dimensions",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "metric_date", "metric_name", "dimensions", name="uq_metric"
        ),
    )
    op.create_index(
        "ix_metric_aggregates_date", "metric_aggregates", ["metric_date"]
    )
    op.create_index(
        "ix_metric_aggregates_name", "metric_aggregates", ["metric_name"]
    )

    op.create_table(
        "retention_cohorts",
        sa.Column("cohort_date", sa.Date, primary_key=True),
        sa.Column("day_number", sa.SmallInteger, primary_key=True),
        sa.Column("cohort_size", sa.Integer, nullable=False),
        sa.Column("returned", sa.Integer, nullable=False),
        sa.Column("retention_pct", sa.Numeric(6, 3), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "aggregation_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("run_type", sa.String(32), nullable=False),
        sa.Column("target_date", sa.Date, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("rows_processed", sa.BigInteger, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_aggregation_runs_target_date", "aggregation_runs", ["target_date"]
    )


def downgrade() -> None:
    op.drop_index("ix_aggregation_runs_target_date", table_name="aggregation_runs")
    op.drop_table("aggregation_runs")
    op.drop_table("retention_cohorts")
    op.drop_index("ix_metric_aggregates_name", table_name="metric_aggregates")
    op.drop_index("ix_metric_aggregates_date", table_name="metric_aggregates")
    op.drop_table("metric_aggregates")
