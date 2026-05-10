from __future__ import annotations

import logging
import signal
import threading

import uvicorn
from fastapi import FastAPI, Response, status

from . import metrics
from .cassandra_client import CassandraClient
from .config import settings
from .consumer import WarehouseConsumer

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("consumer")

app = FastAPI(title="warehouse-consumer")

_cassandra = CassandraClient()
_consumer: WarehouseConsumer | None = None
_consumer_thread: threading.Thread | None = None


@app.on_event("startup")
def _startup() -> None:
    global _consumer, _consumer_thread
    _cassandra.connect()
    _consumer = WarehouseConsumer(_cassandra)
    _consumer_thread = threading.Thread(target=_consumer.start, name="kafka-consumer", daemon=True)
    _consumer_thread.start()

    def _on_sigterm(signum, frame):  # noqa: ANN001
        log.info("got signal %s, stopping", signum)
        if _consumer:
            _consumer.stop()

    signal.signal(signal.SIGTERM, _on_sigterm)


@app.on_event("shutdown")
def _shutdown() -> None:
    if _consumer:
        _consumer.stop()
    if _consumer_thread:
        _consumer_thread.join(timeout=10)
    _cassandra.shutdown()


@app.get("/health")
def health() -> Response:
    kafka_ok = bool(_consumer and _consumer.is_kafka_healthy())
    cassandra_ok = _cassandra.is_healthy()
    if kafka_ok and cassandra_ok:
        return Response(
            content='{"status":"ok","kafka":true,"cassandra":true}',
            media_type="application/json",
            status_code=status.HTTP_200_OK,
        )
    return Response(
        content=f'{{"status":"degraded","kafka":{str(kafka_ok).lower()},"cassandra":{str(cassandra_ok).lower()}}}',
        media_type="application/json",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


@app.get("/metrics")
def metrics_endpoint() -> Response:
    body, ctype = metrics.render()
    return Response(content=body, media_type=ctype)


def run() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.http_host,
        port=settings.http_port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
