from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "cinema-service"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
