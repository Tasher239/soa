from __future__ import annotations

from pydantic_settings import SettingsConfigDict

from cinema_shared.settings import CommonSettings


class ProducerSettings(CommonSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    service_name: str = "cinema-producer"
    port: int = 8000

    kafka_bootstrap_servers: str = "kafka-1:9092,kafka-2:9092"
    schema_registry_host: str = "schema-registry"
    schema_registry_port: int = 8081

    @property
    def schema_registry_url(self) -> str:
        return f"{'http'}://{self.schema_registry_host}:{self.schema_registry_port}"
    kafka_topic: str = "movie-events"
    avro_schema_file: str = "/app/schemas/avro/movie_event.avsc"

    kafka_acks: str = "all"
    kafka_enable_idempotence: bool = True
    kafka_linger_ms: int = 20
    kafka_batch_size: int = 131072
    kafka_compression_type: str = "zstd"
    kafka_queue_buffer_kb: int = 1_048_576
    kafka_delivery_timeout_ms: int = 120_000
    kafka_max_in_flight: int = 5

    generator_enabled: bool = True
    generator_rps: int = 150
    generator_concurrent_users: int = 50
    generator_user_pool: int = 500
    generator_movie_pool: int = 120
    generator_zipf_a: float = 1.25

    retry_attempts: int = 5
    retry_min_seconds: int = 1
    retry_max_seconds: int = 30


settings = ProducerSettings()
