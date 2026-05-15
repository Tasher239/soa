from __future__ import annotations

import logging
import time
from typing import Iterable

from cassandra.cluster import Cluster, Session
from cassandra.policies import DCAwareRoundRobinPolicy, TokenAwarePolicy
from cassandra import ConsistencyLevel
from cassandra.query import BatchStatement, BatchType, PreparedStatement

from .config import settings

log = logging.getLogger(__name__)

_READ_CL = getattr(ConsistencyLevel, settings.cassandra_read_consistency)


class CassandraClient:
    def __init__(self) -> None:
        self._cluster: Cluster | None = None
        self._session: Session | None = None
        self._prepared: dict[str, PreparedStatement] = {}

    def connect(self, attempts: int = 60, delay: float = 5.0) -> None:
        contact_points = [h.strip() for h in settings.cassandra_contact_points.split(",") if h.strip()]
        last_err: Exception | None = None
        for i in range(attempts):
            try:
                cluster = Cluster(
                    contact_points=contact_points,
                    port=settings.cassandra_port,
                    load_balancing_policy=TokenAwarePolicy(
                        DCAwareRoundRobinPolicy(local_dc=settings.cassandra_local_dc)
                    ),
                    protocol_version=5,
                )
                session = cluster.connect(settings.cassandra_keyspace)
                session.default_consistency_level = _READ_CL
                self._cluster = cluster
                self._session = session
                self._prepare_statements()
                log.info("connected to cassandra cluster %s", contact_points)
                return
            except Exception as exc:
                last_err = exc
                log.warning("cassandra connect attempt %d/%d failed: %s", i + 1, attempts, exc)
                time.sleep(delay)
        raise RuntimeError(f"cassandra not reachable after {attempts} attempts: {last_err}")

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("cassandra session not initialised")
        return self._session

    def is_healthy(self) -> bool:
        try:
            self.session.execute("SELECT release_version FROM system.local")
            return True
        except Exception:
            return False

    def _prepare_statements(self) -> None:
        s = self.session
        self._prepared["select_pz"] = s.prepare(
            "SELECT available_quantity, reserved_quantity, last_event_timestamp, supplier_id "
            "FROM inventory_by_product_zone WHERE product_id=? AND zone_id=?"
        )
        self._prepared["select_pz_all_zones"] = s.prepare(
            "SELECT zone_id, available_quantity, reserved_quantity "
            "FROM inventory_by_product_zone WHERE product_id=?"
        )
        self._prepared["upsert_pz"] = s.prepare(
            "UPDATE inventory_by_product_zone "
            "SET available_quantity=?, reserved_quantity=?, last_event_timestamp=?, "
            "    last_event_id=?, supplier_id=? "
            "WHERE product_id=? AND zone_id=?"
        )
        self._prepared["upsert_product"] = s.prepare(
            "UPDATE inventory_by_product "
            "SET total_available_quantity=?, total_reserved_quantity=?, last_event_timestamp=? "
            "WHERE product_id=?"
        )
        self._prepared["upsert_zone"] = s.prepare(
            "UPDATE inventory_by_zone "
            "SET available_quantity=?, reserved_quantity=?, last_event_timestamp=? "
            "WHERE zone_id=? AND product_id=?"
        )
        self._prepared["insert_processed"] = s.prepare(
            "INSERT INTO processed_events (event_id, event_type, processed_at) VALUES (?, ?, ?)"
        )
        self._prepared["select_processed"] = s.prepare(
            "SELECT event_id FROM processed_events WHERE event_id=?"
        )
        self._prepared["insert_history"] = s.prepare(
            "INSERT INTO event_history (product_id, event_timestamp, event_id, event_type, payload) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        self._prepared["upsert_order"] = s.prepare(
            "UPDATE orders SET status=?, items=?, created_at=?, updated_at=? WHERE order_id=?"
        )
        self._prepared["select_order"] = s.prepare(
            "SELECT status, items, created_at, updated_at FROM orders WHERE order_id=?"
        )
        self._prepared["update_order_status"] = s.prepare(
            "UPDATE orders SET status=?, updated_at=? WHERE order_id=?"
        )

    def prep(self, name: str) -> PreparedStatement:
        return self._prepared[name]

    def is_event_processed(self, event_id: str) -> bool:
        rows = self.session.execute(self.prep("select_processed"), (event_id,))
        return rows.one() is not None

    def read_zone_row(self, product_id: str, zone_id: str):
        return self.session.execute(
            self.prep("select_pz"), (product_id, zone_id)
        ).one()

    def read_all_zones(self, product_id: str) -> Iterable:
        return list(self.session.execute(
            self.prep("select_pz_all_zones"), (product_id,)
        ))

    def read_order(self, order_id: str):
        return self.session.execute(self.prep("select_order"), (order_id,)).one()

    def batch(self) -> BatchStatement:
        return BatchStatement(
            batch_type=BatchType.LOGGED,
            consistency_level=ConsistencyLevel.QUORUM,
        )

    def shutdown(self) -> None:
        if self._cluster is not None:
            self._cluster.shutdown()
