import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.booking import BookingORM, BookingStatus


class BookingRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, booking_id: uuid.UUID) -> Optional[BookingORM]:
        result = await self.session.execute(select(BookingORM).where(BookingORM.id == booking_id))
        return result.scalar_one_or_none()

    async def list_by_user_id(self, user_id: uuid.UUID) -> list[BookingORM]:
        result = await self.session.execute(select(BookingORM).where(BookingORM.user_id == user_id))
        return list(result.scalars().all())

    async def create(
        self,
        user_id: uuid.UUID,
        flight_id: int,
        passenger_name: str,
        passenger_email: str,
        seat_count: int,
        total_price: float,
        booking_id: Optional[uuid.UUID] = None,
    ) -> BookingORM:
        booking = BookingORM(
            id=booking_id or uuid.uuid4(),
            user_id=user_id,
            flight_id=flight_id,
            passenger_name=passenger_name,
            passenger_email=passenger_email,
            seat_count=seat_count,
            total_price=total_price,
            status=BookingStatus.CONFIRMED,
        )
        self.session.add(booking)
        await self.session.flush()
        return booking

    async def cancel(self, booking: BookingORM) -> BookingORM:
        booking.status = BookingStatus.CANCELLED
        await self.session.flush()
        return booking
