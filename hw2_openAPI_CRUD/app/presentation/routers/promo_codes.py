from datetime import timezone

from fastapi import APIRouter, Depends, status

from app.application.use_cases.promo_code.create_promo_code import CreatePromoCodeUseCase
from app.domain.entities.promo_code import DiscountType as DomainDiscountType
from app.domain.entities.user import Role, User
from app.infrastructure.repositories.promo_code_repository import SQLAlchemyPromoCodeRepository
from app.presentation.dependencies.auth import require_roles
from app.presentation.dependencies.repositories import get_promo_repo
from generated.models import DiscountType, PromoCodeCreate, PromoCodeResponse

router = APIRouter(prefix="/promo-codes", tags=["promo-codes"])


def _promo_to_response(promo) -> PromoCodeResponse:
    valid_from = promo.valid_from
    valid_until = promo.valid_until
    if valid_from is not None and valid_from.tzinfo is None:
        valid_from = valid_from.replace(tzinfo=timezone.utc)
    if valid_until is not None and valid_until.tzinfo is None:
        valid_until = valid_until.replace(tzinfo=timezone.utc)
    return PromoCodeResponse(
        id=promo.id,
        code=promo.code,
        discount_type=DiscountType(promo.discount_type),
        discount_value=promo.discount_value,
        min_order_amount=promo.min_order_amount,
        max_uses=promo.max_uses,
        current_uses=promo.current_uses,
        valid_from=valid_from,
        valid_until=valid_until,
        active=promo.active,
    )


@router.post("", response_model=PromoCodeResponse, status_code=status.HTTP_201_CREATED)
async def create_promo_code(
    body: PromoCodeCreate,
    _: User = Depends(require_roles(Role.SELLER, Role.ADMIN)),
    promo_repo: SQLAlchemyPromoCodeRepository = Depends(get_promo_repo),
) -> PromoCodeResponse:
    use_case = CreatePromoCodeUseCase(promo_repo)
    promo = await use_case.execute(
        code=body.code,
        discount_type=DomainDiscountType(body.discount_type),
        discount_value=body.discount_value,
        min_order_amount=body.min_order_amount,
        max_uses=body.max_uses,
        valid_from=body.valid_from,
        valid_until=body.valid_until,
    )
    return _promo_to_response(promo)
