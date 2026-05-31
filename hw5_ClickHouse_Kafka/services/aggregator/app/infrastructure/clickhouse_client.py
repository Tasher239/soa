from __future__ import annotations

from typing import Any

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from cinema_shared.logging import get_logger

from app.core.config import settings
from app.domain.exceptions import ClickHouseUnavailable

logger = get_logger("aggregator.clickhouse")


class ClickHouseGateway:
    def __init__(self) -> None:
        self._client: AsyncClient | None = None

    async def connect(self) -> None:
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
                    self._client = await clickhouse_connect.get_async_client(
                        host=settings.clickhouse_host,
                        port=settings.clickhouse_http_port,
                        username=settings.clickhouse_user,
                        password=settings.clickhouse_password,
                        database=settings.clickhouse_database,
                        interface="http",
                        pool_mgr=None,
                    )
        except Exception as exc:
            raise ClickHouseUnavailable(f"clickhouse_connect_failed: {exc}") from exc

        logger.info(
            "clickhouse_connected",
            host=settings.clickhouse_host,
            port=settings.clickhouse_http_port,
            database=settings.clickhouse_database,
        )

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def ping(self) -> bool:
        if self._client is None:
            return False
        try:
            result = await self._client.query("SELECT 1")
            return bool(result.result_rows)
        except Exception:
            return False

    async def query(
        self,
        sql: str,
        parameters: dict[str, Any] | None = None,
    ) -> list[tuple]:
        if self._client is None:
            raise ClickHouseUnavailable("clickhouse_not_connected")
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
                    result = await self._client.query(sql, parameters=parameters)
            return list(result.result_rows)
        except Exception as exc:
            raise ClickHouseUnavailable(f"clickhouse_query_failed: {exc}") from exc
