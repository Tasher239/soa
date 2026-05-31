from __future__ import annotations


class AggregatorError(Exception):
    error_code: str = "AGGREGATOR_ERROR"
    http_status: int = 500

    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NoDataError(AggregatorError):
    error_code = "NO_DATA"
    http_status = 404


class ClickHouseUnavailable(AggregatorError):
    error_code = "CLICKHOUSE_UNAVAILABLE"
    http_status = 503


class PostgresUnavailable(AggregatorError):
    error_code = "POSTGRES_UNAVAILABLE"
    http_status = 503


class S3Unavailable(AggregatorError):
    error_code = "S3_UNAVAILABLE"
    http_status = 503
