from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.metrics import MetricName, MetricPoint
from app.infrastructure.clickhouse_client import ClickHouseGateway

SQL = """
SELECT
    device_type,
    sum(events)              AS events,
    uniqMerge(users_state)   AS users
FROM cinema.daily_device_distribution
WHERE event_date = {d:Date}
GROUP BY device_type
ORDER BY events DESC
"""


async def compute_device_distribution(
    ch: ClickHouseGateway, target: date
) -> list[MetricPoint]:
    rows = await ch.query(SQL, parameters={"d": target})
    points: list[MetricPoint] = []
    for device_type, events, users in rows:
        points.append(
            MetricPoint(
                metric_date=target,
                metric_name=MetricName.DEVICE_EVENTS,
                metric_value=Decimal(int(events)),
                dimensions={"device_type": str(device_type)},
            )
        )
        points.append(
            MetricPoint(
                metric_date=target,
                metric_name=MetricName.DEVICE_USERS,
                metric_value=Decimal(int(users)),
                dimensions={"device_type": str(device_type)},
            )
        )
    return points
