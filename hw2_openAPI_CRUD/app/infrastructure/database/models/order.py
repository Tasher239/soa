import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.infrastructure.database.base import Base


class OrderORM(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        SAEnum(
            "CREATED",
            "PAYMENT_PENDING",
            "PAID",
            "SHIPPED",
            "COMPLETED",
            "CANCELED",
            name="order_status",
        ),
        nullable=False,
        default="CREATED",
        index=True,
    )
    promo_code_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("promo_codes.id"), nullable=True
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["UserORM"] = relationship(back_populates="orders")
    promo_code: Mapped["PromoCodeORM | None"] = relationship(back_populates="orders")
    items: Mapped[list["OrderItemORM"]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
