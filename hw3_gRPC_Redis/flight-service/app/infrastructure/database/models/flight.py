import enum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class FlightStatus(enum.Enum):
    SCHEDULED = "SCHEDULED"
    DEPARTED = "DEPARTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class FlightORM(Base):
    __tablename__ = "flights"
    __table_args__ = (
        CheckConstraint("total_seats > 0", name="ck_flights_total_seats_positive"),
        CheckConstraint("available_seats >= 0", name="ck_flights_available_seats_non_negative"),
        CheckConstraint("available_seats <= total_seats", name="ck_flights_available_seats_not_exceed_total"),
        CheckConstraint("price > 0", name="ck_flights_price_positive"),
        UniqueConstraint("flight_number", "departure_time", name="uq_flights_number_departure"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flight_number: Mapped[str] = mapped_column(String(10), nullable=False)
    origin: Mapped[str] = mapped_column(String(3), nullable=False)
    destination: Mapped[str] = mapped_column(String(3), nullable=False)
    departure_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_time: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    total_seats: Mapped[int] = mapped_column(nullable=False)
    available_seats: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[FlightStatus] = mapped_column(
        Enum(FlightStatus, name="flight_status_enum", create_constraint=False),
        nullable=False,
        server_default="SCHEDULED",
    )

    reservations: Mapped[list] = relationship("SeatReservationORM", back_populates="flight", lazy="noload")
