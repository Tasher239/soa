from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from cassandra.query import BatchStatement

from .cassandra_client import CassandraClient

log = logging.getLogger(__name__)


class ValidationError(Exception):
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


class OutOfOrder(Exception):
    pass


@dataclass
class ProcessResult:
    event_type: str
    applied: bool
    skipped_reason: str | None = None


def _to_dt(ts_ms) -> datetime:
    if isinstance(ts_ms, datetime):
        return ts_ms.replace(tzinfo=timezone.utc) if ts_ms.tzinfo is None else ts_ms.astimezone(timezone.utc)
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)


def _require_positive(qty: int, field: str = "quantity") -> None:
    if qty is None or qty <= 0:
        raise ValidationError("VALIDATION_ERROR", f"Invalid {field}: {qty} (must be positive)")


def _audit(batch: BatchStatement, client: CassandraClient, product_id: str, ts: datetime,
           event_id: str, event_type: str, payload: dict[str, Any]) -> None:
    batch.add(client.prep("insert_history"),
              (product_id, ts, event_id, event_type,
               json.dumps(payload, default=str, ensure_ascii=False)))


def _mark_processed(batch: BatchStatement, client: CassandraClient,
                    event_id: str, event_type: str) -> None:
    batch.add(client.prep("insert_processed"),
              (event_id, event_type, datetime.now(timezone.utc)))


def _check_zone_freshness(client: CassandraClient, product_id: str, zone_id: str,
                          event_ts: datetime) -> tuple[int, int, str | None]:
    row = client.read_zone_row(product_id, zone_id)
    if row is None:
        return 0, 0, None
    if row.last_event_timestamp is not None:
        last_ts = row.last_event_timestamp
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)
        if last_ts >= event_ts:
            raise OutOfOrder(
                f"event_ts={event_ts.isoformat()} <= last={last_ts.isoformat()}"
            )
    return (row.available_quantity or 0, row.reserved_quantity or 0, row.supplier_id)


def _zone_totals_excluding(client: CassandraClient, product_id: str,
                           skip_zones: set[str]) -> tuple[int, int]:
    avail = reserved = 0
    for r in client.read_all_zones(product_id):
        if r.zone_id in skip_zones:
            continue
        avail += r.available_quantity or 0
        reserved += r.reserved_quantity or 0
    return avail, reserved


def _write_zone_state(
    batch: BatchStatement,
    client: CassandraClient,
    *,
    product_id: str,
    zone_id: str,
    new_avail: int,
    new_reserved: int,
    ts: datetime,
    event_id: str,
    supplier_id: str | None,
) -> None:
    batch.add(client.prep("upsert_pz"), (
        new_avail, new_reserved, ts, event_id, supplier_id, product_id, zone_id,
    ))
    batch.add(client.prep("upsert_zone"), (
        new_avail, new_reserved, ts, zone_id, product_id,
    ))


def _write_product_total(
    batch: BatchStatement, client: CassandraClient,
    product_id: str, total_avail: int, total_reserved: int, ts: datetime,
) -> None:
    batch.add(client.prep("upsert_product"), (total_avail, total_reserved, ts, product_id))


def handle_product_received(client: CassandraClient, event: dict[str, Any]) -> ProcessResult:
    qty = event["quantity"]
    _require_positive(qty)
    product_id = event["product_id"]
    zone_id = event["zone_id"]
    ts = _to_dt(event["timestamp"])
    supplier_id = event.get("supplier_id")

    cur_avail, cur_reserved, cur_supplier = _check_zone_freshness(client, product_id, zone_id, ts)
    new_avail = cur_avail + qty
    new_reserved = cur_reserved
    next_supplier = supplier_id if supplier_id is not None else cur_supplier

    other_avail, other_reserved = _zone_totals_excluding(client, product_id, {zone_id})
    total_avail = other_avail + new_avail
    total_reserved = other_reserved + new_reserved

    batch = client.batch()
    _write_zone_state(batch, client,
                      product_id=product_id, zone_id=zone_id,
                      new_avail=new_avail, new_reserved=new_reserved,
                      ts=ts, event_id=event["event_id"], supplier_id=next_supplier)
    _write_product_total(batch, client, product_id, total_avail, total_reserved, ts)
    _audit(batch, client, product_id, ts, event["event_id"], "PRODUCT_RECEIVED", event)
    _mark_processed(batch, client, event["event_id"], "PRODUCT_RECEIVED")
    client.session.execute(batch)
    return ProcessResult("PRODUCT_RECEIVED", True)


def handle_product_shipped(client: CassandraClient, event: dict[str, Any]) -> ProcessResult:
    qty = event["quantity"]
    _require_positive(qty)
    product_id = event["product_id"]
    zone_id = event["zone_id"]
    ts = _to_dt(event["timestamp"])

    cur_avail, cur_reserved, cur_supplier = _check_zone_freshness(client, product_id, zone_id, ts)
    if cur_avail < qty:
        raise ValidationError("INSUFFICIENT_INVENTORY",
                              f"available={cur_avail} < shipped={qty}")
    new_avail = cur_avail - qty
    new_reserved = cur_reserved

    other_avail, other_reserved = _zone_totals_excluding(client, product_id, {zone_id})
    total_avail = other_avail + new_avail
    total_reserved = other_reserved + new_reserved

    batch = client.batch()
    _write_zone_state(batch, client,
                      product_id=product_id, zone_id=zone_id,
                      new_avail=new_avail, new_reserved=new_reserved,
                      ts=ts, event_id=event["event_id"], supplier_id=cur_supplier)
    _write_product_total(batch, client, product_id, total_avail, total_reserved, ts)
    _audit(batch, client, product_id, ts, event["event_id"], "PRODUCT_SHIPPED", event)
    _mark_processed(batch, client, event["event_id"], "PRODUCT_SHIPPED")
    client.session.execute(batch)
    return ProcessResult("PRODUCT_SHIPPED", True)


def handle_product_moved(client: CassandraClient, event: dict[str, Any]) -> ProcessResult:
    qty = event["quantity"]
    _require_positive(qty)
    product_id = event["product_id"]
    from_zone = event["from_zone_id"]
    to_zone = event["to_zone_id"]
    if from_zone == to_zone:
        raise ValidationError("VALIDATION_ERROR", "from_zone == to_zone")
    ts = _to_dt(event["timestamp"])

    f_avail, f_reserved, f_supplier = _check_zone_freshness(client, product_id, from_zone, ts)
    t_avail, t_reserved, t_supplier = _check_zone_freshness(client, product_id, to_zone, ts)
    if f_avail < qty:
        raise ValidationError("INSUFFICIENT_INVENTORY",
                              f"from_zone={from_zone} available={f_avail} < moved={qty}")

    new_f_avail = f_avail - qty
    new_t_avail = t_avail + qty

    other_avail, other_reserved = _zone_totals_excluding(
        client, product_id, {from_zone, to_zone}
    )
    total_avail = other_avail + new_f_avail + new_t_avail
    total_reserved = other_reserved + f_reserved + t_reserved

    batch = client.batch()
    _write_zone_state(batch, client,
                      product_id=product_id, zone_id=from_zone,
                      new_avail=new_f_avail, new_reserved=f_reserved,
                      ts=ts, event_id=event["event_id"], supplier_id=f_supplier)
    _write_zone_state(batch, client,
                      product_id=product_id, zone_id=to_zone,
                      new_avail=new_t_avail, new_reserved=t_reserved,
                      ts=ts, event_id=event["event_id"], supplier_id=t_supplier)
    _write_product_total(batch, client, product_id, total_avail, total_reserved, ts)
    _audit(batch, client, product_id, ts, event["event_id"], "PRODUCT_MOVED", event)
    _mark_processed(batch, client, event["event_id"], "PRODUCT_MOVED")
    client.session.execute(batch)
    return ProcessResult("PRODUCT_MOVED", True)


def handle_product_reserved(client: CassandraClient, event: dict[str, Any]) -> ProcessResult:
    qty = event["quantity"]
    _require_positive(qty)
    product_id = event["product_id"]
    zone_id = event["zone_id"]
    ts = _to_dt(event["timestamp"])

    cur_avail, cur_reserved, cur_supplier = _check_zone_freshness(client, product_id, zone_id, ts)
    if cur_avail < qty:
        raise ValidationError("INSUFFICIENT_INVENTORY",
                              f"available={cur_avail} < requested={qty}")
    new_avail = cur_avail - qty
    new_reserved = cur_reserved + qty

    other_avail, other_reserved = _zone_totals_excluding(client, product_id, {zone_id})
    total_avail = other_avail + new_avail
    total_reserved = other_reserved + new_reserved

    batch = client.batch()
    _write_zone_state(batch, client,
                      product_id=product_id, zone_id=zone_id,
                      new_avail=new_avail, new_reserved=new_reserved,
                      ts=ts, event_id=event["event_id"], supplier_id=cur_supplier)
    _write_product_total(batch, client, product_id, total_avail, total_reserved, ts)
    _audit(batch, client, product_id, ts, event["event_id"], "PRODUCT_RESERVED", event)
    _mark_processed(batch, client, event["event_id"], "PRODUCT_RESERVED")
    client.session.execute(batch)
    return ProcessResult("PRODUCT_RESERVED", True)


def handle_product_released(client: CassandraClient, event: dict[str, Any]) -> ProcessResult:
    qty = event["quantity"]
    _require_positive(qty)
    product_id = event["product_id"]
    zone_id = event["zone_id"]
    ts = _to_dt(event["timestamp"])

    cur_avail, cur_reserved, cur_supplier = _check_zone_freshness(client, product_id, zone_id, ts)
    if cur_reserved < qty:
        raise ValidationError("INSUFFICIENT_RESERVATION",
                              f"reserved={cur_reserved} < released={qty}")
    new_avail = cur_avail + qty
    new_reserved = cur_reserved - qty

    other_avail, other_reserved = _zone_totals_excluding(client, product_id, {zone_id})
    total_avail = other_avail + new_avail
    total_reserved = other_reserved + new_reserved

    batch = client.batch()
    _write_zone_state(batch, client,
                      product_id=product_id, zone_id=zone_id,
                      new_avail=new_avail, new_reserved=new_reserved,
                      ts=ts, event_id=event["event_id"], supplier_id=cur_supplier)
    _write_product_total(batch, client, product_id, total_avail, total_reserved, ts)
    _audit(batch, client, product_id, ts, event["event_id"], "PRODUCT_RELEASED", event)
    _mark_processed(batch, client, event["event_id"], "PRODUCT_RELEASED")
    client.session.execute(batch)
    return ProcessResult("PRODUCT_RELEASED", True)


def handle_inventory_counted(client: CassandraClient, event: dict[str, Any]) -> ProcessResult:
    counted = event["counted_quantity"]
    if counted is None or counted < 0:
        raise ValidationError("VALIDATION_ERROR",
                              f"Invalid counted_quantity: {counted} (must be >= 0)")
    product_id = event["product_id"]
    zone_id = event["zone_id"]
    ts = _to_dt(event["timestamp"])

    _, cur_reserved, cur_supplier = _check_zone_freshness(client, product_id, zone_id, ts)
    new_avail = counted
    new_reserved = cur_reserved

    other_avail, other_reserved = _zone_totals_excluding(client, product_id, {zone_id})
    total_avail = other_avail + new_avail
    total_reserved = other_reserved + new_reserved

    batch = client.batch()
    _write_zone_state(batch, client,
                      product_id=product_id, zone_id=zone_id,
                      new_avail=new_avail, new_reserved=new_reserved,
                      ts=ts, event_id=event["event_id"], supplier_id=cur_supplier)
    _write_product_total(batch, client, product_id, total_avail, total_reserved, ts)
    _audit(batch, client, product_id, ts, event["event_id"], "INVENTORY_COUNTED", event)
    _mark_processed(batch, client, event["event_id"], "INVENTORY_COUNTED")
    client.session.execute(batch)
    return ProcessResult("INVENTORY_COUNTED", True)


def handle_order_created(client: CassandraClient, event: dict[str, Any]) -> ProcessResult:
    items = event.get("items") or []
    if not items:
        raise ValidationError("VALIDATION_ERROR", "order has no items")
    for item in items:
        _require_positive(item["quantity"], "item.quantity")

    order_id = event["order_id"]
    ts = _to_dt(event["timestamp"])

    batch = client.batch()
    items_by_product: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        items_by_product.setdefault(item["product_id"], []).append(item)

    for product_id, prod_items in items_by_product.items():
        touched_zones: dict[str, dict[str, int]] = {}
        cur_supplier_by_zone: dict[str, str | None] = {}
        for item in prod_items:
            zone_id = item["zone_id"]
            qty = item["quantity"]
            if zone_id in touched_zones:
                state = touched_zones[zone_id]
            else:
                cur_avail, cur_reserved, cur_supplier = _check_zone_freshness(
                    client, product_id, zone_id, ts
                )
                cur_supplier_by_zone[zone_id] = cur_supplier
                state = {"avail": cur_avail, "reserved": cur_reserved}
                touched_zones[zone_id] = state
            if state["avail"] < qty:
                raise ValidationError(
                    "INSUFFICIENT_INVENTORY",
                    f"product={product_id} zone={zone_id} available={state['avail']} < requested={qty}",
                )
            state["avail"] -= qty
            state["reserved"] += qty

        other_avail, other_reserved = _zone_totals_excluding(
            client, product_id, set(touched_zones.keys())
        )
        total_avail = other_avail + sum(s["avail"] for s in touched_zones.values())
        total_reserved = other_reserved + sum(s["reserved"] for s in touched_zones.values())

        for zone_id, state in touched_zones.items():
            _write_zone_state(batch, client,
                              product_id=product_id, zone_id=zone_id,
                              new_avail=state["avail"], new_reserved=state["reserved"],
                              ts=ts, event_id=event["event_id"],
                              supplier_id=cur_supplier_by_zone[zone_id])
        _write_product_total(batch, client, product_id, total_avail, total_reserved, ts)
        _audit(batch, client, product_id, ts, event["event_id"], "ORDER_CREATED", event)

    batch.add(client.prep("upsert_order"),
              ("CREATED", json.dumps(items, default=str), ts, ts, order_id))
    _mark_processed(batch, client, event["event_id"], "ORDER_CREATED")
    client.session.execute(batch)
    return ProcessResult("ORDER_CREATED", True)


def handle_order_completed(client: CassandraClient, event: dict[str, Any]) -> ProcessResult:
    order_id = event["order_id"]
    ts = _to_dt(event["timestamp"])

    order_row = client.read_order(order_id)
    if order_row is None:
        raise ValidationError("UNKNOWN_ORDER", f"order_id={order_id} not found")
    if order_row.status == "COMPLETED":
        raise OutOfOrder(f"order_id={order_id} is already COMPLETED")

    items: list[dict[str, Any]] = json.loads(order_row.items) if order_row.items else []

    batch = client.batch()
    items_by_product: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        items_by_product.setdefault(item["product_id"], []).append(item)

    for product_id, prod_items in items_by_product.items():
        touched_zones: dict[str, dict[str, int]] = {}
        cur_supplier_by_zone: dict[str, str | None] = {}
        for item in prod_items:
            zone_id = item["zone_id"]
            qty = item["quantity"]
            if zone_id in touched_zones:
                state = touched_zones[zone_id]
            else:
                cur_avail, cur_reserved, cur_supplier = _check_zone_freshness(
                    client, product_id, zone_id, ts
                )
                cur_supplier_by_zone[zone_id] = cur_supplier
                state = {"avail": cur_avail, "reserved": cur_reserved}
                touched_zones[zone_id] = state
            if state["reserved"] < qty:
                raise ValidationError(
                    "INSUFFICIENT_RESERVATION",
                    f"product={product_id} zone={zone_id} reserved={state['reserved']} < shipped={qty}",
                )
            state["reserved"] -= qty

        other_avail, other_reserved = _zone_totals_excluding(
            client, product_id, set(touched_zones.keys())
        )
        total_avail = other_avail + sum(s["avail"] for s in touched_zones.values())
        total_reserved = other_reserved + sum(s["reserved"] for s in touched_zones.values())

        for zone_id, state in touched_zones.items():
            _write_zone_state(batch, client,
                              product_id=product_id, zone_id=zone_id,
                              new_avail=state["avail"], new_reserved=state["reserved"],
                              ts=ts, event_id=event["event_id"],
                              supplier_id=cur_supplier_by_zone[zone_id])
        _write_product_total(batch, client, product_id, total_avail, total_reserved, ts)
        _audit(batch, client, product_id, ts, event["event_id"], "ORDER_COMPLETED", event)

    batch.add(client.prep("update_order_status"), ("COMPLETED", ts, order_id))
    _mark_processed(batch, client, event["event_id"], "ORDER_COMPLETED")
    client.session.execute(batch)
    return ProcessResult("ORDER_COMPLETED", True)


HANDLERS = {
    "ProductReceived": handle_product_received,
    "ProductShipped": handle_product_shipped,
    "ProductMoved": handle_product_moved,
    "ProductReserved": handle_product_reserved,
    "ProductReleased": handle_product_released,
    "InventoryCounted": handle_inventory_counted,
    "OrderCreated": handle_order_created,
    "OrderCompleted": handle_order_completed,
}

EVENT_TYPE_TO_NAME = {
    "PRODUCT_RECEIVED": "ProductReceived",
    "PRODUCT_SHIPPED": "ProductShipped",
    "PRODUCT_MOVED": "ProductMoved",
    "PRODUCT_RESERVED": "ProductReserved",
    "PRODUCT_RELEASED": "ProductReleased",
    "INVENTORY_COUNTED": "InventoryCounted",
    "ORDER_CREATED": "OrderCreated",
    "ORDER_COMPLETED": "OrderCompleted",
}

NAME_TO_EVENT_TYPE = {v: k for k, v in EVENT_TYPE_TO_NAME.items()}
