from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.metrics import MetricName, MetricPoint
from app.infrastructure.clickhouse_client import ClickHouseGateway

SQL = """
SELECT
    coalesce(sum(finished_count), 0) AS finished,
    coalesce(sum(started_count), 0)  AS started
FROM cinema.daily_user_activity
WHERE event_date = {d:Date}
"""


async def compute_conversion(ch: ClickHouseGateway, target: date) -> MetricPoint:
    rows = await ch.query(SQL, parameters={"d": target})
    finished, started = (rows[0][0], rows[0][1]) if rows else (0, 0)
    if not started:
        value = Decimal("0")
    else:
        value = (Decimal(finished) / Decimal(started)).quantize(Decimal("0.000001"))
    return MetricPoint(
        metric_date=target,
        metric_name=MetricName.CONVERSION,
        metric_value=value,
        dimensions={},
    )
