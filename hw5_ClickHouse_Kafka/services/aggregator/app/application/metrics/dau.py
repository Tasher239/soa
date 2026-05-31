from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.metrics import MetricName, MetricPoint
from app.infrastructure.clickhouse_client import ClickHouseGateway

SQL = """
SELECT uniqMerge(dau_state) AS dau
FROM cinema.daily_user_activity
WHERE event_date = {d:Date}
"""


async def compute_dau(ch: ClickHouseGateway, target: date) -> MetricPoint:
    rows = await ch.query(SQL, parameters={"d": target})
    value = Decimal(int(rows[0][0])) if rows and rows[0][0] is not None else Decimal(0)
    return MetricPoint(
        metric_date=target,
        metric_name=MetricName.DAU,
        metric_value=value,
        dimensions={},
    )
