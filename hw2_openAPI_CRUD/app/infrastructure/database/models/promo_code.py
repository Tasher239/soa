import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database.base import Base


class PromoCodeORM(Base):
    __tablename__ = "promo_codes"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    discount_type: Mapped[str] = mapped_column(
        SAEnum("PERCENTAGE", "FIXED_AMOUNT", name="discount_type"), nullable=False
    )
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_order_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    current_uses: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    valid_from: Mapped[datetime] = mapped_column(nullable=False)
    valid_until: Mapped[datetime] = mapped_column(nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    orders: Mapped[list["OrderORM"]] = relationship(back_populates="promo_code")
