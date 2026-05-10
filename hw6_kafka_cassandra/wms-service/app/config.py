from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    kafka_bootstrap_servers: str = "kafka:9092"
    kafka_topic: str = "warehouse-events"
    schema_registry_url: str = "http://schema-registry:8081"
    schemas_dir: str = "/schemas"

    product_received_schema: str = "v2"

    http_host: str = "0.0.0.0"
    http_port: int = 8001

    log_level: str = "INFO"


settings = Settings()
