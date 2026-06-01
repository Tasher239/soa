from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.metrics import MetricName, MetricPoint
from app.infrastructure.clickhouse_client import ClickHouseGateway

SQL = """
SELECT movie_id, sum(views) AS v
FROM cinema.daily_movie_views
WHERE event_date = {d:Date}
GROUP BY movie_id
ORDER BY v DESC
LIMIT {n:UInt32}
"""


async def compute_top_movies(
    ch: ClickHouseGateway, target: date, limit: int = 10
) -> list[MetricPoint]:
    rows = await ch.query(SQL, parameters={"d": target, "n": limit})
    points: list[MetricPoint] = []
    for rank, (movie_id, views) in enumerate(rows, start=1):
        points.append(
            MetricPoint(
                metric_date=target,
                metric_name=MetricName.TOP_MOVIE_VIEWS,
                metric_value=Decimal(int(views)),
                dimensions={"movie_id": str(movie_id), "rank": rank},
            )
        )
    return points
