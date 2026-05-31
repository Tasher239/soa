"""Unit tests for domain schemas - no external deps."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from cinema_shared.schemas.events import DeviceType, EventType, MovieEventIn


def make_valid_payload(**overrides) -> dict:
    base = {
        "user_id": "user_1",
        "movie_id": "movie_1",
        "event_type": "VIEW_STARTED",
        "device_type": "MOBILE",
        "session_id": "sess_1",
    }
    base.update(overrides)
    return base


def test_valid_event_parses():
    event = MovieEventIn(**make_valid_payload())
    assert event.event_type == EventType.VIEW_STARTED
    assert event.device_type == DeviceType.MOBILE


def test_materialize_assigns_uuid():
    event = MovieEventIn(**make_valid_payload())
    materialized = event.materialize()
    assert isinstance(materialized.event_id, UUID)


def test_materialize_explicit_event_id():
    from uuid import uuid4
    eid = uuid4()
    event = MovieEventIn(**make_valid_payload(event_id=str(eid)))
    materialized = event.materialize()
    assert materialized.event_id == eid


def test_materialize_assigns_timestamp_if_none():
    event = MovieEventIn(**make_valid_payload())
    assert event.timestamp is None
    materialized = event.materialize()
    assert materialized.timestamp is not None
    assert materialized.timestamp.tzinfo is not None


def test_invalid_event_type_rejected():
    with pytest.raises(ValidationError):
        MovieEventIn(**make_valid_payload(event_type="NOT_VALID"))


def test_empty_user_id_rejected():
    with pytest.raises(ValidationError):
        MovieEventIn(**make_valid_payload(user_id=""))


def test_avro_dict_serializable():
    event = MovieEventIn(**make_valid_payload()).materialize()
    d = event.to_avro_dict()
    assert isinstance(d["event_id"], str)
    assert isinstance(d["timestamp"], datetime)
    assert d["event_type"] == "VIEW_STARTED"


def test_timestamp_utc_normalization():
    from datetime import timedelta
    naive = datetime(2024, 1, 1, 12, 0, 0)
    event = MovieEventIn(**make_valid_payload(timestamp=naive.isoformat()))
    assert event.timestamp.tzinfo is not None


def test_all_event_types_valid():
    for et in EventType:
        event = MovieEventIn(**make_valid_payload(event_type=et.value))
        assert event.event_type == et


def test_all_device_types_valid():
    for dt in DeviceType:
        event = MovieEventIn(**make_valid_payload(device_type=dt.value))
        assert event.device_type == dt
