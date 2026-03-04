from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.order import Order
from app.domain.entities.order_item import OrderItem


class IOrderRepository(ABC):
    @abstractmethod
    async def get_by_id(self, order_id: UUID) -> Order | None: ...

    @abstractmethod
    async def find_active_for_user(self, user_id: UUID) -> Order | None:
        ...

    @abstractmethod
    async def create_with_items(
        self,
        order: Order,
        items: list[OrderItem],
    ) -> Order:
        ...

    @abstractmethod
    async def update_items(
        self,
        order: Order,
        new_items: list[OrderItem],
    ) -> Order:
        ...

    @abstractmethod
    async def cancel(self, order: Order) -> Order:
        ...

    @abstractmethod
    async def save(self, order: Order) -> Order:
        ...
