from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.flight import FlightORM, FlightStatus


class FlightRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, flight_id: int) -> Optional[FlightORM]:
        result = await self.session.execute(select(FlightORM).where(FlightORM.id == flight_id))
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, flight_id: int) -> Optional[FlightORM]:
        result = await self.session.execute(
            select(FlightORM).where(FlightORM.id == flight_id).with_for_update()
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        origin: str,
        destination: str,
        departure_date: Optional[date] = None,
    ) -> list[FlightORM]:
        query = select(FlightORM).where(
            FlightORM.origin == origin.upper(),
            FlightORM.destination == destination.upper(),
            FlightORM.status == FlightStatus.SCHEDULED,
        )
        if departure_date:
            from sqlalchemy import func
            query = query.where(
                func.date(FlightORM.departure_time) == departure_date
            )
        result = await self.session.execute(query)
        return list(result.scalars().all())
