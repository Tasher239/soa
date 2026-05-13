from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://flight:flight@flight-db/flight_db"
    REDIS_SENTINEL_HOST: str = "redis-sentinel"
    REDIS_SENTINEL_PORT: int = 26379
    REDIS_MASTER_NAME: str = "mymaster"
    FLIGHT_SERVICE_API_KEY: str = "secret-api-key"
    CACHE_TTL: int = 600
    GRPC_PORT: int = 50051

    class Config:
        env_file = ".env"


settings = Settings()
