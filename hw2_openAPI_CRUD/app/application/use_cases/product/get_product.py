from uuid import UUID

from app.domain.entities.product import Product
from app.domain.exceptions import ProductNotFoundException
from app.domain.repositories.product_repository import IProductRepository


class GetProductUseCase:
    def __init__(self, product_repo: IProductRepository) -> None:
        self._repo = product_repo

    async def execute(self, product_id: UUID) -> Product:
        product = await self._repo.get_by_id(product_id)
        if not product:
            raise ProductNotFoundException(f"Product {product_id} not found")
        return product
