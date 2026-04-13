from uuid import UUID

from app.domain.entities.order import Order, OrderStatus
from app.domain.entities.user import Role, User
from app.domain.exceptions import (
    AccessDeniedException,
    InvalidStateTransitionException,
    OrderNotFoundException,
    OrderOwnershipViolationException,
)
from app.domain.repositories.order_repository import IOrderRepository


_CANCELLABLE_STATES = {OrderStatus.CREATED, OrderStatus.PAYMENT_PENDING}


class CancelOrderUseCase:
    def __init__(self, order_repo: IOrderRepository) -> None:
        self._repo = order_repo

    async def execute(self, order_id: UUID, current_user: User) -> Order:
        order = await self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException(f"Order {order_id} not found")

        if current_user.role == Role.SELLER:
            raise AccessDeniedException("SELLER cannot cancel orders")

        if current_user.role == Role.USER and order.user_id != current_user.id:
            raise OrderOwnershipViolationException(
                "Order does not belong to current user"
            )

        if order.status not in _CANCELLABLE_STATES:
            raise InvalidStateTransitionException(
                f"Cannot cancel order in state {order.status}; "
                "only CREATED or PAYMENT_PENDING are allowed"
            )

        return await self._repo.cancel(order)
