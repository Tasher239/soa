from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.seat_reservation import ReservationStatus, SeatReservationORM


class ReservationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_booking_id(self, booking_id: str) -> Optional[SeatReservationORM]:
        result = await self.session.execute(
            select(SeatReservationORM).where(SeatReservationORM.booking_id == booking_id)
        )
        return result.scalar_one_or_none()

    async def get_active_by_booking_id(self, booking_id: str, for_update: bool = False) -> Optional[SeatReservationORM]:
        query = select(SeatReservationORM).where(
            SeatReservationORM.booking_id == booking_id,
            SeatReservationORM.status == ReservationStatus.ACTIVE,
        )
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create(
        self,
        flight_id: int,
        booking_id: str,
        seat_count: int,
    ) -> SeatReservationORM:
        reservation = SeatReservationORM(
            flight_id=flight_id,
            booking_id=booking_id,
            seat_count=seat_count,
            status=ReservationStatus.ACTIVE,
        )
        self.session.add(reservation)
        await self.session.flush()
        return reservation
