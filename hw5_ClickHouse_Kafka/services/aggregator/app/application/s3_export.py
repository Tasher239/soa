from __future__ import annotations

import io
from datetime import date, datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq
from prometheus_client import Counter
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from cinema_shared.logging import get_logger

from app.core.config import settings
from app.domain.exceptions import NoDataError, S3Unavailable
from app.infrastructure.database.session import AsyncSessionFactory
from app.infrastructure.repositories.aggregates_repo import AggregatesRepository
from app.infrastructure.s3_client import s3_client

logger = get_logger("aggregator.s3_export")

EXPORTS = Counter(
    "cinema_exports_total",
    "Daily aggregate exports to S3",
    ["status"],
)


class ExportDailyAggregates:
    async def execute(self, target: date) -> dict:
        logger.info("export_started", target=str(target))

        async with AsyncSessionFactory() as session:
            repo = AggregatesRepository(session)
            metric_rows = await repo.fetch_metrics_by_date(target)
            retention_rows = await repo.fetch_retention_by_date(target)

        if not metric_rows and not retention_rows:
            EXPORTS.labels("no_data").inc()
            raise NoDataError(f"no aggregates for {target.isoformat()}")

        now_iso = datetime.now(timezone.utc).isoformat()

        rows = []
        for r in metric_rows:
            rows.append({
                "metric_date": r.metric_date,
                "metric_name": r.metric_name,
                "metric_value": float(r.metric_value),
                "dimensions": r.dimensions,
                "computed_at": r.computed_at.isoformat() if r.computed_at else now_iso,
            })
        for r in retention_rows:
            rows.append({
                "metric_date": r.cohort_date,
                "metric_name": "retention",
                "metric_value": float(r.retention_pct),
                "dimensions": {
                    "day_number": r.day_number,
                    "cohort_size": r.cohort_size,
                    "returned": r.returned,
                },
                "computed_at": r.computed_at.isoformat() if r.computed_at else now_iso,
            })

        table = pa.Table.from_pylist(rows)
        buf = io.BytesIO()
        pq.write_table(table, buf, compression="snappy")
        payload = buf.getvalue()

        key = f"daily/{target.isoformat()}/aggregates.parquet"
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(settings.retry_attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=settings.retry_min_seconds,
                    max=settings.retry_max_seconds,
                ),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    async with s3_client() as s3:
                        await s3.put_object(
                            Bucket=settings.s3_bucket,
                            Key=key,
                            Body=payload,
                            ContentType="application/octet-stream",
                        )
        except Exception as exc:
            EXPORTS.labels("failed").inc()
            raise S3Unavailable(f"s3_upload_failed: {exc}") from exc

        EXPORTS.labels("success").inc()
        logger.info(
            "export_finished",
            target=str(target),
            bucket=settings.s3_bucket,
            key=key,
            bytes=len(payload),
            rows=len(rows),
        )
        return {
            "bucket": settings.s3_bucket,
            "key": key,
            "bytes": len(payload),
            "rows": len(rows),
            "target_date": target.isoformat(),
        }
