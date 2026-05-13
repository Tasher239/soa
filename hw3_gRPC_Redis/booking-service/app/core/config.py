from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://booking:booking@booking-db/booking_db"
    FLIGHT_SERVICE_HOST: str = "flight-service"
    FLIGHT_SERVICE_PORT: int = 50051
    FLIGHT_SERVICE_API_KEY: str = "secret-api-key"
    CB_FAILURE_THRESHOLD: int = 5
    CB_TIMEOUT: int = 30
    CB_WINDOW: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
