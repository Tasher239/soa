from app.domain.entities.product import Product, ProductStatus
from app.domain.repositories.product_repository import IProductRepository


class ListProductsUseCase:
    def __init__(self, product_repo: IProductRepository) -> None:
        self._repo = product_repo

    async def execute(
        self,
        page: int,
        size: int,
        status: ProductStatus | None = None,
        category: str | None = None,
    ) -> tuple[list[Product], int]:
        return await self._repo.list(
            page=page, size=size, status=status, category=category,
            exclude_archived=(status is None),
        )
