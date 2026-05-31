from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.metrics import MetricName, MetricPoint
from app.infrastructure.clickhouse_client import ClickHouseGateway

SQL = """
SELECT coalesce(avgMerge(avg_watch_state), 0) AS avg_watch
FROM cinema.daily_user_activity
WHERE event_date = {d:Date}
"""


async def compute_avg_watch_time(ch: ClickHouseGateway, target: date) -> MetricPoint:
    rows = await ch.query(SQL, parameters={"d": target})
    raw = rows[0][0] if rows else 0
    value = Decimal(str(raw or 0)).quantize(Decimal("0.000001"))
    return MetricPoint(
        metric_date=target,
        metric_name=MetricName.AVG_WATCH_SECONDS,
        metric_value=value,
        dimensions={},
    )
