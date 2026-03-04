import logging.config

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.domain.exceptions import DomainException
from app.presentation.error_handlers import domain_exception_handler, validation_exception_handler
from app.presentation.middleware.logging_middleware import LoggingMiddleware
from app.presentation.routers import auth, orders, products, promo_codes

logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "format": "%(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["console"],
        },
    }
)

app = FastAPI(
    title="Marketplace API",
    version="1.0.0",
    description="Marketplace API with product catalog, orders, promo codes, and JWT auth.",
)

app.add_middleware(LoggingMiddleware)

app.add_exception_handler(DomainException, domain_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.include_router(auth.router)
app.include_router(products.router)
app.include_router(orders.router)
app.include_router(promo_codes.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
