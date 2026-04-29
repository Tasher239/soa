from __future__ import annotations

from datetime import date, timedelta
from typing import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from cinema_shared.logging import get_logger

from app.application.compute_daily import ComputeDailyAggregates
from app.application.s3_export import ExportDailyAggregates
from app.core.config import settings

logger = get_logger("aggregator.scheduler")


class AggregationScheduler:
    def __init__(
        self,
        compute: ComputeDailyAggregates,
        export: ExportDailyAggregates,
    ) -> None:
        self._compute = compute
        self._export = export
        self._scheduler = AsyncIOScheduler(timezone=settings.aggregation_timezone)

    def start(self) -> None:
        self._scheduler.add_job(
            self._run_aggregation,
            trigger=CronTrigger.from_crontab(settings.aggregation_cron, timezone=settings.aggregation_timezone),
            id="aggregation",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self._scheduler.add_job(
            self._run_export,
            trigger=CronTrigger.from_crontab(
                settings.aggregation_s3_export_cron, timezone=settings.aggregation_timezone
            ),
            id="s3_export",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        self._scheduler.start()
        logger.info(
            "scheduler_started",
            aggregation_cron=settings.aggregation_cron,
            export_cron=settings.aggregation_s3_export_cron,
            timezone=settings.aggregation_timezone,
        )

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("scheduler_stopped")

    async def _run_aggregation(self) -> None:
        today = date.today()
        yesterday = today - timedelta(days=1)
        for target in (today, yesterday):
            try:
                await self._compute.execute(target, run_type="scheduled")
            except Exception:
                logger.exception("scheduled_aggregation_failed", target=str(target))

    async def _run_export(self) -> None:
        target = date.today() - timedelta(days=1)
        try:
            await self._export.execute(target)
        except Exception:
            logger.exception("scheduled_export_failed", target=str(target))
