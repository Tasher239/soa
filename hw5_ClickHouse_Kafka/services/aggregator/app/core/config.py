from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from cinema_shared.settings import CommonSettings


class AggregatorSettings(CommonSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "cinema-aggregator"
    port: int = 8001

    database_url: str = (
        "postgresql+asyncpg://cinema:cinema@postgres:5432/cinema"
    )
    pg_pool_size: int = 10
    pg_max_overflow: int = 20

    clickhouse_host: str = "clickhouse"
    clickhouse_http_port: int = 8123
    clickhouse_user: str = "default"
    clickhouse_password: str = ""
    clickhouse_database: str = "cinema"

    s3_endpoint: str = "http://minio:9000"
    s3_bucket: str = "movie-analytics"
    s3_region: str = "us-east-1"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"

    aggregation_cron: str = "5 * * * *"
    aggregation_s3_export_cron: str = "30 0 * * *"
    aggregation_timezone: str = "UTC"

    retry_attempts: int = 3
    retry_min_seconds: int = 2
    retry_max_seconds: int = 20

    retention_window_days: int = 7
    cohort_heatmap_window: int = 14


settings = AggregatorSettings()
