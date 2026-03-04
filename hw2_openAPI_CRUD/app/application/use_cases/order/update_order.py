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
from app.domain.entities.user import Role, User
from app.domain.entities.user_operation import OperationType
from app.domain.exceptions import (
    AccessDeniedException,
    InsufficientStockException,
    InvalidStateTransitionException,
    OrderLimitExceededException,
    OrderNotFoundException,
    OrderOwnershipViolationException,
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


class UpdateOrderUseCase:
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
        order_id: UUID,
        current_user: User,
        new_items: list[OrderItemInput],
    ) -> Order:
        now = datetime.now(timezone.utc)

        order = await self._order_repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException(f"Order {order_id} not found")

        if current_user.role == Role.SELLER:
            raise AccessDeniedException("SELLER cannot update orders")

        if current_user.role == Role.USER and order.user_id != current_user.id:
            raise OrderOwnershipViolationException(
                "Order does not belong to current user"
            )

        if order.status != OrderStatus.CREATED:
            raise InvalidStateTransitionException(
                f"Cannot update order in state {order.status}; only CREATED is allowed"
            )

        last_op = await self._user_op_repo.get_last(
            current_user.id, OperationType.UPDATE_ORDER
        )
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
                    "Please wait before updating another order",
                    details={"retry_after_seconds": remaining},
                )

        products: dict[UUID, object] = {}
        stock_failures = []

        for item in new_items:
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
                order_id=order_id,
                product_id=item.product_id,
                quantity=item.quantity,
                price_at_order=products[item.product_id].price,
            )
            for item in new_items
        ]

        raw_total = sum(oi.price_at_order * oi.quantity for oi in order_items)
        discount = Decimal("0")
        promo_code_id: UUID | None = None

        if order.promo_code_id:
            code = await self._get_promo_code_code(order.promo_code_id)
            promo = await self._promo_repo.get_by_code(code) if code else None
            if promo and promo.is_usable(now) and raw_total >= promo.min_order_amount:
                if promo.discount_type == DiscountType.PERCENTAGE:
                    pct = min(promo.discount_value, _MAX_PERCENTAGE_DISCOUNT)
                    discount = (raw_total * pct / Decimal("100")).quantize(Decimal("0.01"))
                else:
                    discount = min(promo.discount_value, raw_total)
                promo_code_id = promo.id
            else:
                if promo and order.promo_code_id:
                    await self._promo_repo.decrement_uses(order.promo_code_id)
                promo_code_id = None

        total_amount = (raw_total - discount).quantize(Decimal("0.01"))

        order.total_amount = total_amount
        order.discount_amount = discount.quantize(Decimal("0.01"))
        order.promo_code_id = promo_code_id

        updated = await self._order_repo.update_items(order, order_items)

        await self._user_op_repo.record(current_user.id, OperationType.UPDATE_ORDER)

        return updated

    async def _get_promo_code_code(self, promo_code_id: UUID) -> str | None:
        return await self._promo_repo.get_code_by_id(promo_code_id)
