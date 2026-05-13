import enum
import uuid

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.base import Base


class BookingStatus(enum.Enum):
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class BookingORM(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint("seat_count > 0", name="ck_bookings_seat_count_positive"),
        CheckConstraint("total_price > 0", name="ck_bookings_total_price_positive"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    flight_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    passenger_name: Mapped[str] = mapped_column(String(255), nullable=False)
    passenger_email: Mapped[str] = mapped_column(String(255), nullable=False)
    seat_count: Mapped[int] = mapped_column(nullable=False)
    total_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status_enum", create_constraint=False),
        nullable=False,
        server_default="CONFIRMED",
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
