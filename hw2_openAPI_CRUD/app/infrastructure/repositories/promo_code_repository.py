from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.promo_code import DiscountType, PromoCode
from app.domain.repositories.promo_code_repository import IPromoCodeRepository
from app.infrastructure.database.models.promo_code import PromoCodeORM


def _to_domain(orm: PromoCodeORM) -> PromoCode:
    return PromoCode(
        id=orm.id,
        code=orm.code,
        discount_type=DiscountType(orm.discount_type),
        discount_value=orm.discount_value,
        min_order_amount=orm.min_order_amount,
        max_uses=orm.max_uses,
        current_uses=orm.current_uses,
        valid_from=orm.valid_from,
        valid_until=orm.valid_until,
        active=orm.active,
    )


class SQLAlchemyPromoCodeRepository(IPromoCodeRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: str) -> PromoCode | None:
        result = await self._session.execute(
            select(PromoCodeORM).where(PromoCodeORM.code == code)
        )
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def create(self, promo: PromoCode) -> PromoCode:
        orm = PromoCodeORM(
            id=promo.id,
            code=promo.code,
            discount_type=promo.discount_type,
            discount_value=promo.discount_value,
            min_order_amount=promo.min_order_amount,
            max_uses=promo.max_uses,
            current_uses=0,
            valid_from=promo.valid_from,
            valid_until=promo.valid_until,
            active=promo.active,
        )
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return _to_domain(orm)

    async def increment_uses(self, promo_id: UUID) -> None:
        await self._session.execute(
            update(PromoCodeORM)
            .where(PromoCodeORM.id == promo_id)
            .values(current_uses=PromoCodeORM.current_uses + 1)
        )

    async def get_code_by_id(self, promo_id: UUID) -> str | None:
        result = await self._session.execute(
            select(PromoCodeORM.code).where(PromoCodeORM.id == promo_id)
        )
        return result.scalar_one_or_none()

    async def decrement_uses(self, promo_id: UUID) -> None:
        await self._session.execute(
            update(PromoCodeORM)
            .where(PromoCodeORM.id == promo_id)
            .values(current_uses=PromoCodeORM.current_uses - 1)
        )
