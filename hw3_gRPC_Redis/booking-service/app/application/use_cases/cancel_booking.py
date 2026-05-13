import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import BookingAlreadyCancelledError, BookingNotFoundError
from app.infrastructure.database.models.booking import BookingStatus
from app.infrastructure.grpc_client.flight_client import flight_client
from app.infrastructure.repositories.booking_repository import BookingRepository

logger = logging.getLogger(__name__)


async def cancel_booking(session: AsyncSession, booking_id: uuid.UUID):
    async with session.begin():
        repo = BookingRepository(session)
        booking = await repo.get_by_id(booking_id)

        if booking is None:
            raise BookingNotFoundError(str(booking_id))

        if booking.status == BookingStatus.CANCELLED:
            raise BookingAlreadyCancelledError(str(booking_id))

        try:
            await flight_client.release_reservation(str(booking_id))
        except Exception as e:
            logger.warning(f"Failed to release reservation for booking {booking_id}: {e}")

        booking = await repo.cancel(booking)

    logger.info(f"Booking cancelled: id={booking_id}")
    return booking
