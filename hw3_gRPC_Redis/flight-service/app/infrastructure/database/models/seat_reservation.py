import enum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base


class ReservationStatus(enum.Enum):
    ACTIVE = "ACTIVE"
    RELEASED = "RELEASED"
    EXPIRED = "EXPIRED"


class SeatReservationORM(Base):
    __tablename__ = "seat_reservations"
    __table_args__ = (
        UniqueConstraint("booking_id", name="uq_seat_reservations_booking_id"),
        CheckConstraint("seat_count > 0", name="ck_seat_reservations_seat_count_positive"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flight_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("flights.id", ondelete="CASCADE"), nullable=False)
    booking_id: Mapped[str] = mapped_column(String(36), nullable=False)
    seat_count: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus, name="reservation_status_enum", create_constraint=False),
        nullable=False,
        server_default="ACTIVE",
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    flight: Mapped["FlightORM"] = relationship("FlightORM", back_populates="reservations")
