import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from app.core.config import settings
from app.domain.entities.order import Order, OrderStatus
from app.domain.entities.order_item import OrderItem
from app.domain.entities.promo_code import DiscountType
from app.domain.entities.product import ProductStatus
from app.domain.entities.user_operation import OperationType
from app.domain.exceptions import (
    InsufficientStockException,
    OrderHasActiveException,
    OrderLimitExceededException,
    ProductInactiveException,
    ProductNotFoundException,
    PromoCodeInvalidException,
    PromoCodeMinAmountException,
)
from app.domain.repositories.order_repository import IOrderRepository
from app.domain.repositories.product_repository import IProductRepository
from app.domain.repositories.promo_code_repository import IPromoCodeRepository
from app.domain.repositories.user_operation_repository import IUserOperationRepository

_MAX_PERCENTAGE_DISCOUNT = Decimal("70")


@dataclass
class OrderItemInput:
    product_id: UUID
    quantity: int


class CreateOrderUseCase:
    def __init__(
        self,
        order_repo: IOrderRepository,
        product_repo: IProductRepository,
        promo_repo: IPromoCodeRepository,
        user_op_repo: IUserOperationRepository,
    ) -> None:
        self._order_repo = order_repo
        self._product_repo = product_repo
        self._promo_repo = promo_repo
        self._user_op_repo = user_op_repo

    async def execute(
        self,
        user_id: UUID,
        items: list[OrderItemInput],
        promo_code_str: str | None,
    ) -> Order:
        now = datetime.now(timezone.utc)

        last_op = await self._user_op_repo.get_last(user_id, OperationType.CREATE_ORDER)
        if last_op:
            last_op_time = last_op.created_at
            if last_op_time.tzinfo is None:
                last_op_time = last_op_time.replace(tzinfo=timezone.utc)
            if (now - last_op_time) < timedelta(minutes=settings.rate_limit_minutes):
                remaining = int(
                    (timedelta(minutes=settings.rate_limit_minutes) - (now - last_op_time))
                    .total_seconds()
                )
                raise OrderLimitExceededException(
                    "Please wait before creating another order",
                    details={"retry_after_seconds": remaining},
                )

        active = await self._order_repo.find_active_for_user(user_id)
        if active:
            raise OrderHasActiveException("User already has an active order")

        products: dict[UUID, object] = {}
        stock_failures = []

        for item in items:
            product = await self._product_repo.get_by_id(item.product_id)
            if not product:
                raise ProductNotFoundException(
                    f"Product {item.product_id} not found"
                )
            if product.status != ProductStatus.ACTIVE:
                raise ProductInactiveException(
                    f"Product {item.product_id} is not active"
                )
            if product.stock < item.quantity:
                stock_failures.append(
                    {
                        "product_id": str(item.product_id),
                        "requested": item.quantity,
                        "available": product.stock,
                    }
                )
            products[item.product_id] = product

        if stock_failures:
            raise InsufficientStockException(
                "Insufficient stock for some items",
                details={"items": stock_failures},
            )

        order_items = [
            OrderItem(
                id=uuid.uuid4(),
                order_id=uuid.uuid4(),  # placeholder; overwritten by repo
                product_id=item.product_id,
                quantity=item.quantity,
                price_at_order=products[item.product_id].price,
            )
            for item in items
        ]

        raw_total = sum(
            oi.price_at_order * oi.quantity for oi in order_items
        )
        discount = Decimal("0")
        promo_code_id: UUID | None = None

        if promo_code_str:
            promo = await self._promo_repo.get_by_code(promo_code_str)
            if not promo or not promo.is_usable(now):
                raise PromoCodeInvalidException(
                    "Promo code is invalid, expired, or exhausted"
                )
            if raw_total < promo.min_order_amount:
                raise PromoCodeMinAmountException(
                    "Order total is below minimum for this promo code",
                    details={
                        "min_order_amount": float(promo.min_order_amount),
                        "current_total": float(raw_total),
                    },
                )
            if promo.discount_type == DiscountType.PERCENTAGE:
                pct = min(promo.discount_value, _MAX_PERCENTAGE_DISCOUNT)
                discount = (raw_total * pct / Decimal("100")).quantize(Decimal("0.01"))
            else:
                discount = min(promo.discount_value, raw_total)

            promo_code_id = promo.id
            await self._promo_repo.increment_uses(promo.id)

        total_amount = (raw_total - discount).quantize(Decimal("0.01"))

        order = Order(
            id=uuid.uuid4(),
            user_id=user_id,
            status=OrderStatus.CREATED,
            total_amount=total_amount,
            discount_amount=discount.quantize(Decimal("0.01")),
            promo_code_id=promo_code_id,
            created_at=None,  # type: ignore[arg-type]
            updated_at=None,  # type: ignore[arg-type]
            items=order_items,
        )

        created = await self._order_repo.create_with_items(order, order_items)

        await self._user_op_repo.record(user_id, OperationType.CREATE_ORDER)

        return created
