import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.grpc_client.flight_client import flight_client
from app.infrastructure.repositories.booking_repository import BookingRepository

logger = logging.getLogger(__name__)


async def create_booking(
    session: AsyncSession,
    user_id: uuid.UUID,
    flight_id: int,
    passenger_name: str,
    passenger_email: str,
    seat_count: int,
):
    # Step 1: Get flight info — validates flight exists and gets price
    flight = await flight_client.get_flight(flight_id)

    # Generate booking_id upfront: used as idempotency key for ReserveSeats
    booking_id = str(uuid.uuid4())

    # Step 2: Reserve seats atomically in Flight Service
    reservation_id = await flight_client.reserve_seats(flight_id, seat_count, booking_id)

    # Step 3: Price snapshot
    total_price = seat_count * flight.price

    # Step 4: Persist booking — only after successful reservation
    async with session.begin():
        repo = BookingRepository(session)
        booking = await repo.create(
            booking_id=uuid.UUID(booking_id),
            user_id=user_id,
            flight_id=flight_id,
            passenger_name=passenger_name,
            passenger_email=passenger_email,
            seat_count=seat_count,
            total_price=total_price,
        )

    logger.info(
        f"Booking created: id={booking_id}, flight={flight_id}, "
        f"seats={seat_count}, reservation={reservation_id}, price={total_price}"
    )
    return booking
