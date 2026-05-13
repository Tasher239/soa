import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import grpc
import grpc.aio

from app.core.config import settings
from app.domain.exceptions import (
    FlightNotFoundError,
    NoSeatsAvailableError,
    ServiceUnavailableError,
)
from app.generated import flight_pb2, flight_pb2_grpc
from app.infrastructure.grpc_client.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class FlightInfo:
    id: int
    flight_number: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    total_seats: int
    available_seats: int
    price: float
    status: str


def _proto_to_flight_info(f: flight_pb2.Flight) -> FlightInfo:
    status_map = {0: "SCHEDULED", 1: "DEPARTED", 2: "CANCELLED", 3: "COMPLETED"}
    return FlightInfo(
        id=f.id,
        flight_number=f.flight_number,
        origin=f.origin,
        destination=f.destination,
        departure_time=f.departure_time.ToDatetime(),
        arrival_time=f.arrival_time.ToDatetime(),
        total_seats=f.total_seats,
        available_seats=f.available_seats,
        price=f.price,
        status=status_map.get(f.status, "SCHEDULED"),
    )


_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.CB_FAILURE_THRESHOLD,
    timeout=settings.CB_TIMEOUT,
)


def _get_channel() -> grpc.aio.Channel:
    target = f"{settings.FLIGHT_SERVICE_HOST}:{settings.FLIGHT_SERVICE_PORT}"
    return grpc.aio.insecure_channel(target)


def _get_metadata() -> list[tuple[str, str]]:
    return [("x-api-key", settings.FLIGHT_SERVICE_API_KEY)]


class FlightGrpcClient:
    async def get_flight(self, flight_id: int) -> FlightInfo:
        async def _call():
            async with _get_channel() as channel:
                stub = flight_pb2_grpc.FlightServiceStub(channel)
                try:
                    response = await stub.GetFlight(
                        flight_pb2.GetFlightRequest(flight_id=flight_id),
                        metadata=_get_metadata(),
                    )
                    return _proto_to_flight_info(response.flight)
                except grpc.aio.AioRpcError as e:
                    if e.code() == grpc.StatusCode.NOT_FOUND:
                        raise FlightNotFoundError(flight_id)
                    if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                        raise
                    raise ServiceUnavailableError(str(e))

        return await _circuit_breaker.call(_call)

    async def search_flights(
        self,
        origin: str,
        destination: str,
        date: Optional[str] = None,
    ) -> list[FlightInfo]:
        async def _call():
            async with _get_channel() as channel:
                stub = flight_pb2_grpc.FlightServiceStub(channel)
                try:
                    response = await stub.SearchFlights(
                        flight_pb2.SearchFlightsRequest(
                            origin=origin,
                            destination=destination,
                            date=date or "",
                        ),
                        metadata=_get_metadata(),
                    )
                    return [_proto_to_flight_info(f) for f in response.flights]
                except grpc.aio.AioRpcError as e:
                    if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                        raise
                    raise ServiceUnavailableError(str(e))

        return await _circuit_breaker.call(_call)

    async def reserve_seats(
        self,
        flight_id: int,
        seat_count: int,
        booking_id: str,
    ) -> int:
        async def _call():
            async with _get_channel() as channel:
                stub = flight_pb2_grpc.FlightServiceStub(channel)
                try:
                    response = await stub.ReserveSeats(
                        flight_pb2.ReserveSeatsRequest(
                            flight_id=flight_id,
                            seat_count=seat_count,
                            booking_id=booking_id,
                        ),
                        metadata=_get_metadata(),
                    )
                    return response.reservation_id
                except grpc.aio.AioRpcError as e:
                    if e.code() == grpc.StatusCode.NOT_FOUND:
                        raise FlightNotFoundError(flight_id)
                    if e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
                        raise NoSeatsAvailableError(flight_id)
                    if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                        raise
                    raise ServiceUnavailableError(str(e))

        return await _circuit_breaker.call(_call)

    async def release_reservation(self, booking_id: str) -> bool:
        async def _call():
            async with _get_channel() as channel:
                stub = flight_pb2_grpc.FlightServiceStub(channel)
                try:
                    response = await stub.ReleaseReservation(
                        flight_pb2.ReleaseReservationRequest(booking_id=booking_id),
                        metadata=_get_metadata(),
                    )
                    return response.success
                except grpc.aio.AioRpcError as e:
                    if e.code() in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED):
                        raise
                    raise ServiceUnavailableError(str(e))

        return await _circuit_breaker.call(_call)


flight_client = FlightGrpcClient()
