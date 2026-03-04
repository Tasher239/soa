from uuid import UUID

from app.domain.entities.order import Order
from app.domain.entities.user import Role, User
from app.domain.exceptions import (
    AccessDeniedException,
    OrderNotFoundException,
    OrderOwnershipViolationException,
)
from app.domain.repositories.order_repository import IOrderRepository


class GetOrderUseCase:
    def __init__(self, order_repo: IOrderRepository) -> None:
        self._repo = order_repo

    async def execute(self, order_id: UUID, current_user: User) -> Order:
        order = await self._repo.get_by_id(order_id)
        if not order:
            raise OrderNotFoundException(f"Order {order_id} not found")

        if current_user.role == Role.SELLER:
            raise AccessDeniedException("SELLER cannot view orders")

        if current_user.role == Role.USER and order.user_id != current_user.id:
            raise OrderOwnershipViolationException(
                "Order does not belong to current user"
            )

        return order
