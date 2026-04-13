from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.order import Order, OrderStatus
from app.domain.entities.order_item import OrderItem
from app.domain.repositories.order_repository import IOrderRepository
from app.infrastructure.database.models.order import OrderORM
from app.infrastructure.database.models.order_item import OrderItemORM
from app.infrastructure.database.models.promo_code import PromoCodeORM
from app.infrastructure.database.models.product import ProductORM


def _item_to_domain(orm: OrderItemORM) -> OrderItem:
    return OrderItem(
        id=orm.id,
        order_id=orm.order_id,
        product_id=orm.product_id,
        quantity=orm.quantity,
        price_at_order=orm.price_at_order,
    )


def _to_domain(orm: OrderORM) -> Order:
    return Order(
        id=orm.id,
        user_id=orm.user_id,
        status=OrderStatus(orm.status),
        total_amount=orm.total_amount,
        discount_amount=orm.discount_amount,
        promo_code_id=orm.promo_code_id,
        created_at=orm.created_at,
        updated_at=orm.updated_at,
        items=[_item_to_domain(i) for i in (orm.items or [])],
    )


class SQLAlchemyOrderRepository(IOrderRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, order_id: UUID) -> Order | None:
        result = await self._session.execute(
            select(OrderORM).where(OrderORM.id == order_id)
        )
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def find_active_for_user(self, user_id: UUID) -> Order | None:
        result = await self._session.execute(
            select(OrderORM).where(
                OrderORM.user_id == user_id,
                OrderORM.status.in_(
                    [OrderStatus.CREATED, OrderStatus.PAYMENT_PENDING]
                ),
            )
        )
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def create_with_items(
        self,
        order: Order,
        items: list[OrderItem],
    ) -> Order:
        orm_order = OrderORM(
            id=order.id,
            user_id=order.user_id,
            status=order.status,
            promo_code_id=order.promo_code_id,
            total_amount=order.total_amount,
            discount_amount=order.discount_amount,
        )
        self._session.add(orm_order)
        await self._session.flush()

        for item in items:
            orm_item = OrderItemORM(
                id=item.id,
                order_id=orm_order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price_at_order=item.price_at_order,
            )
            self._session.add(orm_item)
            await self._session.execute(
                update(ProductORM)
                .where(ProductORM.id == item.product_id)
                .values(stock=ProductORM.stock - item.quantity)
            )

        await self._session.flush()
        await self._session.refresh(orm_order)
        return _to_domain(orm_order)

    async def update_items(
        self,
        order: Order,
        new_items: list[OrderItem],
    ) -> Order:
        result = await self._session.execute(
            select(OrderORM).where(OrderORM.id == order.id)
        )
        orm_order = result.scalar_one()

        old_items_result = await self._session.execute(
            select(OrderItemORM).where(OrderItemORM.order_id == order.id)
        )
        for old_item in old_items_result.scalars():
            await self._session.execute(
                update(ProductORM)
                .where(ProductORM.id == old_item.product_id)
                .values(stock=ProductORM.stock + old_item.quantity)
            )
            await self._session.delete(old_item)

        await self._session.flush()

        for item in new_items:
            orm_item = OrderItemORM(
                id=item.id,
                order_id=order.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price_at_order=item.price_at_order,
            )
            self._session.add(orm_item)
            await self._session.execute(
                update(ProductORM)
                .where(ProductORM.id == item.product_id)
                .values(stock=ProductORM.stock - item.quantity)
            )

        orm_order.total_amount = order.total_amount
        orm_order.discount_amount = order.discount_amount
        orm_order.promo_code_id = order.promo_code_id

        await self._session.flush()
        await self._session.refresh(orm_order)
        return _to_domain(orm_order)

    async def cancel(self, order: Order) -> Order:
        result = await self._session.execute(
            select(OrderORM).where(OrderORM.id == order.id)
        )
        orm_order = result.scalar_one()

        items_result = await self._session.execute(
            select(OrderItemORM).where(OrderItemORM.order_id == order.id)
        )
        for item in items_result.scalars():
            await self._session.execute(
                update(ProductORM)
                .where(ProductORM.id == item.product_id)
                .values(stock=ProductORM.stock + item.quantity)
            )

        if orm_order.promo_code_id is not None:
            await self._session.execute(
                update(PromoCodeORM)
                .where(PromoCodeORM.id == orm_order.promo_code_id)
                .values(current_uses=PromoCodeORM.current_uses - 1)
            )

        orm_order.status = OrderStatus.CANCELED
        await self._session.flush()
        await self._session.refresh(orm_order)
        return _to_domain(orm_order)

    async def save(self, order: Order) -> Order:
        result = await self._session.execute(
            select(OrderORM).where(OrderORM.id == order.id)
        )
        orm_order = result.scalar_one()
        orm_order.status = order.status
        orm_order.total_amount = order.total_amount
        orm_order.discount_amount = order.discount_amount
        orm_order.promo_code_id = order.promo_code_id
        await self._session.flush()
        await self._session.refresh(orm_order)
        return _to_domain(orm_order)
