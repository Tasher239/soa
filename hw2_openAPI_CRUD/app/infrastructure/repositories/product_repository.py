import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.product import Product, ProductStatus
from app.domain.repositories.product_repository import IProductRepository
from app.infrastructure.database.models.product import ProductORM


def _to_domain(orm: ProductORM) -> Product:
    return Product(
        id=orm.id,
        name=orm.name,
        description=orm.description,
        price=orm.price,
        stock=orm.stock,
        category=orm.category,
        status=ProductStatus(orm.status),
        seller_id=orm.seller_id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
    )


class SQLAlchemyProductRepository(IProductRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, product_id: UUID) -> Product | None:
        result = await self._session.execute(
            select(ProductORM).where(ProductORM.id == product_id)
        )
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def list(
        self,
        page: int,
        size: int,
        status: ProductStatus | None = None,
        category: str | None = None,
        exclude_archived: bool = False,
    ) -> tuple[list[Product], int]:
        q = select(ProductORM)
        if status is not None:
            q = q.where(ProductORM.status == status)
        if exclude_archived:
            q = q.where(ProductORM.status != ProductStatus.ARCHIVED)
        if category is not None:
            q = q.where(ProductORM.category == category)

        count_result = await self._session.execute(
            select(func.count()).select_from(q.subquery())
        )
        total = count_result.scalar_one()

        q = q.offset(page * size).limit(size).order_by(ProductORM.created_at.desc())
        rows = await self._session.execute(q)
        return [_to_domain(r) for r in rows.scalars()], total

    async def create(self, product: Product) -> Product:
        orm = ProductORM(
            id=product.id,
            name=product.name,
            description=product.description,
            price=product.price,
            stock=product.stock,
            category=product.category,
            status=product.status,
            seller_id=product.seller_id,
        )
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return _to_domain(orm)

    async def update(self, product: Product) -> Product:
        result = await self._session.execute(
            select(ProductORM).where(ProductORM.id == product.id)
        )
        orm = result.scalar_one()
        orm.name = product.name
        orm.description = product.description
        orm.price = product.price
        orm.stock = product.stock
        orm.category = product.category
        orm.status = product.status
        await self._session.flush()
        await self._session.refresh(orm)
        return _to_domain(orm)

    async def soft_delete(self, product_id: UUID) -> Product:
        result = await self._session.execute(
            select(ProductORM).where(ProductORM.id == product_id)
        )
        orm = result.scalar_one()
        orm.status = ProductStatus.ARCHIVED
        await self._session.flush()
        await self._session.refresh(orm)
        return _to_domain(orm)

    async def decrement_stock(self, product_id: UUID, quantity: int) -> None:
        await self._session.execute(
            update(ProductORM)
            .where(ProductORM.id == product_id)
            .values(stock=ProductORM.stock - quantity)
        )

    async def increment_stock(self, product_id: UUID, quantity: int) -> None:
        await self._session.execute(
            update(ProductORM)
            .where(ProductORM.id == product_id)
            .values(stock=ProductORM.stock + quantity)
        )
