import uuid
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.domain.entities.promo_code import DiscountType, PromoCode
from app.domain.exceptions import ConflictException
from app.domain.repositories.promo_code_repository import IPromoCodeRepository


class CreatePromoCodeUseCase:
    def __init__(self, promo_repo: IPromoCodeRepository) -> None:
        self._repo = promo_repo

    async def execute(
        self,
        code: str,
        discount_type: DiscountType,
        discount_value: Decimal,
        min_order_amount: Decimal,
        max_uses: int,
        valid_from: datetime,
        valid_until: datetime,
    ) -> PromoCode:
        existing = await self._repo.get_by_code(code)
        if existing:
            raise ConflictException(f"Promo code '{code}' already exists")

        promo = PromoCode(
            id=uuid.uuid4(),
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            min_order_amount=min_order_amount,
            max_uses=max_uses,
            current_uses=0,
            valid_from=valid_from,
            valid_until=valid_until,
            active=True,
        )
        return await self._repo.create(promo)
