import logging

from fastapi import FastAPI

from app.presentation.routers import bookings, flights

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

app = FastAPI(
    title="Booking Service API",
    version="1.0.0",
    description="Flight booking system — REST API for managing bookings.",
)

app.include_router(flights.router)
app.include_router(bookings.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
