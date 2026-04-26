from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.domain.metrics import RetentionCohort
from app.infrastructure.clickhouse_client import ClickHouseGateway

SQL = """
WITH
    {d:Date} AS cohort_d,
    (
        SELECT groupArray(user_id)
        FROM (
            SELECT user_id
            FROM cinema.user_first_seen
            FINAL
            WHERE first_date = cohort_d
        )
    ) AS cohort_users,
    length(cohort_users) AS cohort_size
SELECT
    day_number,
    cohort_size AS cohort,
    uniq(user_id) AS returned
FROM
(
    SELECT
        seen.user_id AS user_id,
        toUInt8(dateDiff('day', cohort_d, seen.event_date)) AS day_number
    FROM cinema.daily_user_seen AS seen
    WHERE
        has(cohort_users, seen.user_id)
        AND seen.event_date BETWEEN cohort_d AND addDays(cohort_d, {window:UInt8})
    GROUP BY seen.user_id, day_number
)
GROUP BY day_number
ORDER BY day_number
"""


async def compute_retention(
    ch: ClickHouseGateway, cohort_date: date, window_days: int = 7
) -> list[RetentionCohort]:
    rows = await ch.query(
        SQL, parameters={"d": cohort_date, "window": window_days}
    )
    seen: dict[int, tuple[int, int]] = {}
    cohort_size = 0
    for day, size, returned in rows:
        cohort_size = int(size)
        seen[int(day)] = (cohort_size, int(returned))

    result: list[RetentionCohort] = []
    for day_number in range(window_days + 1):
        size, returned = seen.get(day_number, (cohort_size, 0))
        if size:
            pct = (Decimal(returned) / Decimal(size) * Decimal(100)).quantize(Decimal("0.001"))
        else:
            pct = Decimal("0")
        result.append(
            RetentionCohort(
                cohort_date=cohort_date,
                day_number=day_number,
                cohort_size=size,
                returned=returned,
                retention_pct=pct,
            )
        )
    return result
