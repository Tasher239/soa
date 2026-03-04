from uuid import UUID

from app.domain.entities.product import Product
from app.domain.entities.user import Role, User
from app.domain.exceptions import AccessDeniedException, ProductNotFoundException
from app.domain.repositories.product_repository import IProductRepository


class DeleteProductUseCase:
    def __init__(self, product_repo: IProductRepository) -> None:
        self._repo = product_repo

    async def execute(self, product_id: UUID, current_user: User) -> Product:
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise ProductNotFoundException(f"Product {product_id} not found")

        if current_user.role == Role.SELLER and product.seller_id != current_user.id:
            raise AccessDeniedException("SELLER can only delete their own products")

        return await self._repo.soft_delete(product_id)
