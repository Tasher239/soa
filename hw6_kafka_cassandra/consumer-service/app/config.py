from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_topic: str = "warehouse-events"
    kafka_dlq_topic: str = "warehouse-events-dlq"
    kafka_group_id: str = "warehouse-state-consumer"
    schema_registry_url: str = "http://schema-registry:8081"

    cassandra_contact_points: str = "cassandra-1,cassandra-2,cassandra-3"
    cassandra_port: int = 9042
    cassandra_keyspace: str = "warehouse"
    cassandra_local_dc: str = "datacenter1"
    cassandra_read_consistency: str = "QUORUM"

    http_host: str = "0.0.0.0"
    http_port: int = 8000

    poll_timeout_seconds: float = 1.0
    lag_refresh_seconds: float = 5.0

    log_level: str = "INFO"

    class Config:
        env_prefix = ""
        env_file = ".env"


settings = Settings()
