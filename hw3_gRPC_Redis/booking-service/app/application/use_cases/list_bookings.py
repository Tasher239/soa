import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.repositories.booking_repository import BookingRepository


async def list_bookings(session: AsyncSession, user_id: uuid.UUID):
    async with session.begin():
        repo = BookingRepository(session)
        return await repo.list_by_user_id(user_id)
