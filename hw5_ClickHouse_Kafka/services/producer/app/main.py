from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
import asyncio
from cinema_shared.avro_loader import load_avro_schema
from cinema_shared.logging import configure_logging, get_logger
from cinema_shared.metrics import build_metrics_router
from cinema_shared.request_id import RequestIdMiddleware

from app.application.publish_event import PublishEventUseCase
from app.application.session_simulator import SessionSimulator
from app.core.config import settings
from app.domain.exceptions import ProducerError
from app.infra.kafka_producer import AvroKafkaProducer
from app.presentation.error_handlers import (
    producer_error_handler,
    validation_error_handler,
)
from app.presentation.api.events.resources import router as events_router
from app.presentation.api.generator.resources import router as generator_router
from app.presentation.api.health.resources import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.service_name, settings.log_level)
    log = get_logger("producer.main")

    avro_schema_str = load_avro_schema(settings.avro_schema_file)
    kafka_producer = AvroKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        topic=settings.kafka_topic,
        schema_registry_url=settings.schema_registry_url,
        avro_schema_str=avro_schema_str,
    )

    kafka_producer.start(asyncio.get_event_loop())

    publish_event = PublishEventUseCase(kafka_producer)
    simulator = SessionSimulator(publish_event)

    app.state.kafka_producer = kafka_producer
    app.state.publish_event = publish_event
    app.state.simulator = simulator

    if settings.generator_enabled:
        await simulator.start()

    log.info(
        "producer_ready",
        topic=settings.kafka_topic,
        bootstrap=settings.kafka_bootstrap_servers,
        generator_enabled=settings.generator_enabled,
    )

    try:
        yield
    finally:
        log.info("producer_shutting_down")
        await simulator.stop()
        await kafka_producer.stop()
        log.info("producer_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Cinema Movie Events Producer",
        version="1.0.0",
        description=(
            "FastAPI ingestion service that publishes user interaction events to Kafka. "
            "Includes a realistic session simulator for demo load."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(RequestIdMiddleware)

    app.add_exception_handler(ProducerError, producer_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)

    app.include_router(events_router, prefix="/events", tags=["events"])
    app.include_router(generator_router, prefix="/generator", tags=["generator"])
    app.include_router(health_router, tags=["health"])
    app.include_router(build_metrics_router())

    return app


app = create_app()
