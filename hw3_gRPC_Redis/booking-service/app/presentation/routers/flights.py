from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.domain.exceptions import FlightNotFoundError, ServiceUnavailableError
from app.infrastructure.grpc_client.flight_client import flight_client

router = APIRouter(prefix="/flights", tags=["flights"])


class FlightResponse(BaseModel):
    id: int
    flight_number: str
    origin: str
    destination: str
    departure_time: str
    arrival_time: str
    total_seats: int
    available_seats: int
    price: float
    status: str


def _to_response(f) -> FlightResponse:
    return FlightResponse(
        id=f.id,
        flight_number=f.flight_number,
        origin=f.origin,
        destination=f.destination,
        departure_time=f.departure_time.isoformat(),
        arrival_time=f.arrival_time.isoformat(),
        total_seats=f.total_seats,
        available_seats=f.available_seats,
        price=f.price,
        status=f.status,
    )


@router.get("", response_model=list[FlightResponse])
async def search_flights(
    origin: str = Query(..., description="IATA origin code"),
    destination: str = Query(..., description="IATA destination code"),
    date: Optional[str] = Query(None, description="Departure date YYYY-MM-DD"),
):
    try:
        flights = await flight_client.search_flights(origin, destination, date)
        return [_to_response(f) for f in flights]
    except ServiceUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/{flight_id}", response_model=FlightResponse)
async def get_flight(flight_id: int):
    try:
        flight = await flight_client.get_flight(flight_id)
        return _to_response(flight)
    except FlightNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ServiceUnavailableError as e:
        raise HTTPException(status_code=503, detail=str(e))
