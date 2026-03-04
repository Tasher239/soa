from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.product import Product, ProductStatus


class IProductRepository(ABC):
    @abstractmethod
    async def get_by_id(self, product_id: UUID) -> Product | None: ...

    @abstractmethod
    async def list(
        self,
        page: int,
        size: int,
        status: ProductStatus | None = None,
        category: str | None = None,
        exclude_archived: bool = False,
    ) -> tuple[list[Product], int]:
        ...

    @abstractmethod
    async def create(self, product: Product) -> Product: ...

    @abstractmethod
    async def update(self, product: Product) -> Product: ...

    @abstractmethod
    async def soft_delete(self, product_id: UUID) -> Product: ...

    @abstractmethod
    async def decrement_stock(self, product_id: UUID, quantity: int) -> None: ...

    @abstractmethod
    async def increment_stock(self, product_id: UUID, quantity: int) -> None: ...
