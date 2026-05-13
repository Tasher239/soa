import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.exceptions import BookingNotFoundError
from app.infrastructure.repositories.booking_repository import BookingRepository


async def get_booking(session: AsyncSession, booking_id: uuid.UUID):
    async with session.begin():
        repo = BookingRepository(session)
        booking = await repo.get_by_id(booking_id)

    if booking is None:
        raise BookingNotFoundError(str(booking_id))

    return booking
