from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Literal

import uvicorn
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from .config import settings
from .producer import WarehouseProducer

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger("wms")

app = FastAPI(title="warehouse-wms")
_producer: WarehouseProducer | None = None


def _now_ms() -> int:
    return int(time.time() * 1000)


def _event_id() -> str:
    return str(uuid.uuid4())


@app.on_event("startup")
def _startup() -> None:
    global _producer
    _producer = WarehouseProducer()
    for attempt in range(30):
        try:
            ids = _producer.register_all()
            log.info("schemas registered: %s", ids)
            break
        except Exception as exc:
            log.warning("schema registry not ready (attempt %d): %s", attempt + 1, exc)
            time.sleep(2)


@app.on_event("shutdown")
def _shutdown() -> None:
    if _producer:
        _producer.close()


class ProductReceivedReq(BaseModel):
    event_id: str | None = None
    timestamp: int | None = None
    product_id: str
    zone_id: str
    quantity: int
    supplier_id: str | None = None
    schema_version: Literal["v1", "v2"] = "v2"


class ProductShippedReq(BaseModel):
    event_id: str | None = None
    timestamp: int | None = None
    product_id: str
    zone_id: str
    quantity: int


class ProductMovedReq(BaseModel):
    event_id: str | None = None
    timestamp: int | None = None
    product_id: str
    from_zone_id: str
    to_zone_id: str
    quantity: int


class ProductReservedReq(BaseModel):
    event_id: str | None = None
    timestamp: int | None = None
    product_id: str
    zone_id: str
    quantity: int
    order_id: str | None = None


class ProductReleasedReq(ProductReservedReq):
    pass


class InventoryCountedReq(BaseModel):
    event_id: str | None = None
    timestamp: int | None = None
    product_id: str
    zone_id: str
    counted_quantity: int


class OrderItemModel(BaseModel):
    product_id: str
    zone_id: str
    quantity: int


class OrderCreatedReq(BaseModel):
    event_id: str | None = None
    timestamp: int | None = None
    order_id: str
    items: list[OrderItemModel]


class OrderCompletedReq(BaseModel):
    event_id: str | None = None
    timestamp: int | None = None
    order_id: str


class RawReq(BaseModel):
    hex: str
    key: str | None = None


def _send(record_name: str, schema_filename: str, body: dict[str, Any], key: str) -> dict[str, Any]:
    if _producer is None:
        raise HTTPException(status_code=503, detail="producer not initialised")
    body["event_id"] = body.get("event_id") or _event_id()
    body["timestamp"] = body.get("timestamp") or _now_ms()
    try:
        partition, offset, schema_id = _producer.publish(record_name, schema_filename, body, key=key)
    except Exception as exc:
        log.exception("publish failed")
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "event_id": body["event_id"],
        "timestamp": body["timestamp"],
        "partition": partition,
        "offset": offset,
        "schema_id": schema_id,
        "record": record_name,
    }


@app.post("/events/product-received", status_code=status.HTTP_202_ACCEPTED)
def product_received(req: ProductReceivedReq) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_id": req.event_id or _event_id(),
        "timestamp": req.timestamp or _now_ms(),
        "product_id": req.product_id,
        "zone_id": req.zone_id,
        "quantity": req.quantity,
    }
    if req.schema_version == "v2":
        payload["supplier_id"] = req.supplier_id
        schema_filename = "product_received_v2.avsc"
    else:
        schema_filename = "product_received_v1.avsc"
    return _send("ProductReceived", schema_filename, payload, key=req.product_id)


@app.post("/events/product-shipped", status_code=status.HTTP_202_ACCEPTED)
def product_shipped(req: ProductShippedReq) -> dict[str, Any]:
    return _send("ProductShipped", "product_shipped.avsc", req.model_dump(exclude_none=False),
                 key=req.product_id)


@app.post("/events/product-moved", status_code=status.HTTP_202_ACCEPTED)
def product_moved(req: ProductMovedReq) -> dict[str, Any]:
    return _send("ProductMoved", "product_moved.avsc", req.model_dump(exclude_none=False),
                 key=req.product_id)


@app.post("/events/product-reserved", status_code=status.HTTP_202_ACCEPTED)
def product_reserved(req: ProductReservedReq) -> dict[str, Any]:
    return _send("ProductReserved", "product_reserved.avsc", req.model_dump(exclude_none=False),
                 key=req.product_id)


@app.post("/events/product-released", status_code=status.HTTP_202_ACCEPTED)
def product_released(req: ProductReleasedReq) -> dict[str, Any]:
    return _send("ProductReleased", "product_released.avsc", req.model_dump(exclude_none=False),
                 key=req.product_id)


@app.post("/events/inventory-counted", status_code=status.HTTP_202_ACCEPTED)
def inventory_counted(req: InventoryCountedReq) -> dict[str, Any]:
    return _send("InventoryCounted", "inventory_counted.avsc", req.model_dump(exclude_none=False),
                 key=req.product_id)


@app.post("/events/order-created", status_code=status.HTTP_202_ACCEPTED)
def order_created(req: OrderCreatedReq) -> dict[str, Any]:
    body = req.model_dump(exclude_none=False)
    body["items"] = [i.model_dump() for i in req.items]
    return _send("OrderCreated", "order_created.avsc", body, key=req.order_id)


@app.post("/events/order-completed", status_code=status.HTTP_202_ACCEPTED)
def order_completed(req: OrderCompletedReq) -> dict[str, Any]:
    return _send("OrderCompleted", "order_completed.avsc", req.model_dump(exclude_none=False),
                 key=req.order_id)


@app.post("/events/raw", status_code=status.HTTP_202_ACCEPTED)
def raw_event(req: RawReq) -> dict[str, Any]:
    if _producer is None:
        raise HTTPException(status_code=503, detail="producer not initialised")
    _producer.publish_raw(bytes.fromhex(req.hex), key=req.key)
    return {"status": "sent", "bytes": len(req.hex) // 2}


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


def run() -> None:
    uvicorn.run("app.main:app", host=settings.http_host, port=settings.http_port,
                log_level=settings.log_level.lower())


if __name__ == "__main__":
    run()
