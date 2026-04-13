from decimal import Decimal
from uuid import UUID

from app.domain.entities.product import Product, ProductStatus
from app.domain.entities.user import Role, User
from app.domain.exceptions import AccessDeniedException, ProductNotFoundException
from app.domain.repositories.product_repository import IProductRepository


class UpdateProductUseCase:
    def __init__(self, product_repo: IProductRepository) -> None:
        self._repo = product_repo

    async def execute(
        self,
        product_id: UUID,
        current_user: User,
        name: str | None = None,
        description: str | None = None,
        price: Decimal | None = None,
        stock: int | None = None,
        category: str | None = None,
        status: ProductStatus | None = None,
    ) -> Product:
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise ProductNotFoundException(f"Product {product_id} not found")

        if current_user.role == Role.SELLER and product.seller_id != current_user.id:
            raise AccessDeniedException("SELLER can only update their own products")

        if name is not None:
            product.name = name
        if description is not None:
            product.description = description
        if price is not None:
            product.price = price
        if stock is not None:
            product.stock = stock
        if category is not None:
            product.category = category
        if status is not None:
            product.status = status

        return await self._repo.update(product)
