import uuid
from uuid import UUID

from app.domain.entities.product import Product, ProductStatus
from app.domain.entities.user import Role, User
from app.domain.exceptions import AccessDeniedException, ProductNotFoundException
from app.domain.repositories.product_repository import IProductRepository


class CreateProductUseCase:
    def __init__(self, product_repo: IProductRepository) -> None:
        self._repo = product_repo

    async def execute(
        self,
        name: str,
        price,
        stock: int,
        category: str,
        status: ProductStatus,
        current_user: User,
        description: str | None = None,
    ) -> Product:
        product = Product(
            id=uuid.uuid4(),
            name=name,
            description=description,
            price=price,
            stock=stock,
            category=category,
            status=status,
            seller_id=current_user.id,
            created_at=None,
            updated_at=None,
        )
        return await self._repo.create(product)
