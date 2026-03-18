import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.use_cases.cancel_booking import cancel_booking
from app.application.use_cases.create_booking import create_booking
from app.application.use_cases.get_booking import get_booking
from app.application.use_cases.list_bookings import list_bookings
from app.domain.exceptions import (
    BookingAlreadyCancelledError,
    BookingNotFoundError,
    FlightNotFoundError,
    NoSeatsAvailableError,
    ServiceUnavailableError,
)
from app.infrastructure.database.session import get_session

router = APIRouter(prefix="/bookings", tags=["bookings"])


class CreateBookingRequest(BaseModel):
    user_id: uuid.UUID
    flight_id: int
    passenger_name: str
    passenger_email: str
    seat_count: int


class BookingResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    flight_id: int
    passenger_name: str
    passenger_email: str
    seat_count: int
    total_price: float
    status: str
    created_at: str
    updated_at: str


def _to_response(b) -> BookingResponse:
    return BookingResponse(
        id=b.id,
        user_id=b.user_id,
        flight_id=b.flight_id,
        passenger_name=b.passenger_name,
        passenger_email=b.passenger_email,
        seat_count=b.seat_count,
        total_price=float(b.total_price),
        status=b.status.value,
        created_at=b.created_at.isoformat(),
        updated_at=b.updated_at.isoformat(),
    )


@router.post("", response_model=BookingResponse, status_code=201)
async def create_booking_endpoint(
    body: CreateBookingRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        booking = await create_booking(
            session=session,
            user_id=body.user_id,
            flight_id=body.flight_id,
            passenger_name=body.passenger_name,
            passenger_email=body.passenger_email,
            seat_count=body.seat_count,
        )
        return _to_response(booking)
    except FlightNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except NoSeatsAvailableError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ServiceUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("", response_model=list[BookingResponse])
async def list_bookings_endpoint(
    user_id: uuid.UUID = Query(..., description="User UUID"),
    session: AsyncSession = Depends(get_session),
):
    bookings = await list_bookings(session=session, user_id=user_id)
    return [_to_response(b) for b in bookings]


@router.get("/{booking_id}", response_model=BookingResponse)
async def get_booking_endpoint(
    booking_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    try:
        booking = await get_booking(session=session, booking_id=booking_id)
        return _to_response(booking)
    except BookingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{booking_id}/cancel", response_model=BookingResponse)
async def cancel_booking_endpoint(
    booking_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    try:
        booking = await cancel_booking(session=session, booking_id=booking_id)
        return _to_response(booking)
    except BookingNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except BookingAlreadyCancelledError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ServiceUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
