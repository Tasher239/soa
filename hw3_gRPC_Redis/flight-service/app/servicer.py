import logging
import re
from datetime import date
from typing import Optional

_IATA_RE = re.compile(r'^[A-Z]{3}$')

import grpc
from google.protobuf.timestamp_pb2 import Timestamp

from app.generated import flight_pb2, flight_pb2_grpc
from app.infrastructure.database.models.seat_reservation import ReservationStatus
from app.infrastructure.database.session import AsyncSessionFactory
from app.infrastructure.redis_client.cache import cache_service
from app.infrastructure.repositories.flight_repository import FlightRepository
from app.infrastructure.repositories.reservation_repository import ReservationRepository

logger = logging.getLogger(__name__)


def _flight_orm_to_dict(flight_orm) -> dict:
    dep = Timestamp()
    dep.FromDatetime(flight_orm.departure_time)
    arr = Timestamp()
    arr.FromDatetime(flight_orm.arrival_time)
    return {
        "id": flight_orm.id,
        "flight_number": flight_orm.flight_number,
        "origin": flight_orm.origin,
        "destination": flight_orm.destination,
        "departure_time": {"seconds": dep.seconds, "nanos": dep.nanos},
        "arrival_time": {"seconds": arr.seconds, "nanos": arr.nanos},
        "total_seats": flight_orm.total_seats,
        "available_seats": flight_orm.available_seats,
        "price": float(flight_orm.price),
        "status": flight_orm.status.value,
    }


def _dict_to_flight_proto(d: dict) -> flight_pb2.Flight:
    dep = Timestamp(seconds=d["departure_time"]["seconds"], nanos=d["departure_time"]["nanos"])
    arr = Timestamp(seconds=d["arrival_time"]["seconds"], nanos=d["arrival_time"]["nanos"])
    status_map = {"SCHEDULED": 0, "DEPARTED": 1, "CANCELLED": 2, "COMPLETED": 3}
    return flight_pb2.Flight(
        id=d["id"],
        flight_number=d["flight_number"],
        origin=d["origin"],
        destination=d["destination"],
        departure_time=dep,
        arrival_time=arr,
        total_seats=d["total_seats"],
        available_seats=d["available_seats"],
        price=d["price"],
        status=status_map.get(d["status"], 0),
    )



class FlightServiceServicer(flight_pb2_grpc.FlightServiceServicer):
    async def GetFlight(self, request, context):
        flight_id = request.flight_id

        cached = cache_service.get_flight(flight_id)
        if cached:
            return flight_pb2.GetFlightResponse(flight=_dict_to_flight_proto(cached))

        async with AsyncSessionFactory() as session:
            repo = FlightRepository(session)
            flight = await repo.get_by_id(flight_id)
            if flight is not None:
                data = _flight_orm_to_dict(flight)
            else:
                data = None

        if data is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, f"Flight {flight_id} not found")
            return
        cache_service.set_flight(flight_id, data)
        return flight_pb2.GetFlightResponse(flight=_dict_to_flight_proto(data))

    async def SearchFlights(self, request, context):
        origin = request.origin.upper()
        destination = request.destination.upper()
        date_str = request.date or None

        if not _IATA_RE.match(origin):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid IATA code for origin: '{origin}' (expected 3 uppercase Latin letters)")
            return
        if not _IATA_RE.match(destination):
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid IATA code for destination: '{destination}' (expected 3 uppercase Latin letters)")
            return

        departure_date: Optional[date] = None
        if date_str:
            try:
                departure_date = date.fromisoformat(date_str)
            except ValueError:
                await context.abort(grpc.StatusCode.INVALID_ARGUMENT, f"Invalid date format: {date_str}")
                return

        cached = cache_service.get_search(origin, destination, date_str)
        if cached is not None:
            flights = [_dict_to_flight_proto(d) for d in cached]
            return flight_pb2.SearchFlightsResponse(flights=flights)

        async with AsyncSessionFactory() as session:
            repo = FlightRepository(session)
            flights_orm = await repo.search(origin, destination, departure_date)
            result = [_flight_orm_to_dict(f) for f in flights_orm]
        cache_service.set_search(origin, destination, date_str, result)
        flights_proto = [_dict_to_flight_proto(d) for d in result]
        return flight_pb2.SearchFlightsResponse(flights=flights_proto)

    async def ReserveSeats(self, request, context):
        flight_id = request.flight_id
        seat_count = request.seat_count
        booking_id = request.booking_id

        async with AsyncSessionFactory() as session:
            async with session.begin():
                res_repo = ReservationRepository(session)

                existing = await res_repo.get_active_by_booking_id(booking_id)
                if existing:
                    logger.info(f"ReserveSeats idempotent: booking_id={booking_id}, reservation_id={existing.id}")
                    return flight_pb2.ReserveSeatsResponse(reservation_id=existing.id)

                flight_repo = FlightRepository(session)
                flight = await flight_repo.get_by_id_for_update(flight_id)

                if flight is None:
                    await context.abort(grpc.StatusCode.NOT_FOUND, f"Flight {flight_id} not found")
                    return

                if flight.available_seats < seat_count:
                    await context.abort(
                        grpc.StatusCode.RESOURCE_EXHAUSTED,
                        f"Not enough seats: available={flight.available_seats}, requested={seat_count}",
                    )
                    return

                flight.available_seats -= seat_count
                reservation = await res_repo.create(flight_id, booking_id, seat_count)
                flight_origin = flight.origin
                flight_destination = flight.destination
                reservation_id = reservation.id

        cache_service.invalidate_flight(flight_id)
        cache_service.invalidate_search_by_flight(flight_origin, flight_destination)

        logger.info(f"ReserveSeats: flight={flight_id}, seats={seat_count}, booking={booking_id}, reservation={reservation_id}")
        return flight_pb2.ReserveSeatsResponse(reservation_id=reservation_id)

    async def ReleaseReservation(self, request, context):
        booking_id = request.booking_id

        async with AsyncSessionFactory() as session:
            async with session.begin():
                res_repo = ReservationRepository(session)
                reservation = await res_repo.get_active_by_booking_id(booking_id, for_update=True)

                if reservation is None:
                    await context.abort(grpc.StatusCode.NOT_FOUND, f"Active reservation for booking {booking_id} not found")
                    return

                flight_repo = FlightRepository(session)
                flight = await flight_repo.get_by_id_for_update(reservation.flight_id)

                if flight is None:
                    await context.abort(grpc.StatusCode.NOT_FOUND, f"Flight {reservation.flight_id} not found")
                    return

                flight.available_seats += reservation.seat_count
                reservation.status = ReservationStatus.RELEASED
                released_flight_id = reservation.flight_id
                released_seats = reservation.seat_count
                flight_origin = flight.origin
                flight_destination = flight.destination

        cache_service.invalidate_flight(released_flight_id)
        cache_service.invalidate_search_by_flight(flight_origin, flight_destination)

        logger.info(f"ReleaseReservation: booking={booking_id}, seats_returned={released_seats}")
        return flight_pb2.ReleaseReservationResponse(success=True)
