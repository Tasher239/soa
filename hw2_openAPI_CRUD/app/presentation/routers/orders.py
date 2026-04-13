from datetime import timezone
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.application.use_cases.order.cancel_order import CancelOrderUseCase
from app.application.use_cases.order.create_order import CreateOrderUseCase, OrderItemInput
from app.application.use_cases.order.get_order import GetOrderUseCase
from app.application.use_cases.order.update_order import UpdateOrderUseCase
from app.application.use_cases.order.update_order import OrderItemInput as UpdateOrderItemInput
from app.domain.entities.user import Role, User
from app.infrastructure.repositories.order_repository import SQLAlchemyOrderRepository
from app.infrastructure.repositories.product_repository import SQLAlchemyProductRepository
from app.infrastructure.repositories.promo_code_repository import SQLAlchemyPromoCodeRepository
from app.infrastructure.repositories.user_operation_repository import SQLAlchemyUserOperationRepository
from app.presentation.dependencies.auth import get_current_user, require_roles
from app.presentation.dependencies.repositories import (
    get_order_repo,
    get_product_repo,
    get_promo_repo,
    get_user_op_repo,
)
from generated.models import (
    OrderCreate,
    OrderItemResponse,
    OrderResponse,
    OrderStatus,
    OrderUpdate,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def _order_to_response(order) -> OrderResponse:
    created_at = order.created_at
    updated_at = order.updated_at
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        status=OrderStatus(order.status),
        items=[
            OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                quantity=item.quantity,
                price_at_order=item.price_at_order,
            )
            for item in order.items
        ],
        total_amount=order.total_amount,
        discount_amount=order.discount_amount,
        promo_code_id=order.promo_code_id,
        created_at=created_at,
        updated_at=updated_at,
    )


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreate,
    current_user: User = Depends(require_roles(Role.USER, Role.ADMIN)),
    order_repo: SQLAlchemyOrderRepository = Depends(get_order_repo),
    product_repo: SQLAlchemyProductRepository = Depends(get_product_repo),
    promo_repo: SQLAlchemyPromoCodeRepository = Depends(get_promo_repo),
    user_op_repo: SQLAlchemyUserOperationRepository = Depends(get_user_op_repo),
) -> OrderResponse:
    use_case = CreateOrderUseCase(order_repo, product_repo, promo_repo, user_op_repo)
    order = await use_case.execute(
        user_id=current_user.id,
        items=[OrderItemInput(product_id=i.product_id, quantity=i.quantity) for i in body.items],
        promo_code_str=body.promo_code,
    )
    return _order_to_response(order)


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    order_repo: SQLAlchemyOrderRepository = Depends(get_order_repo),
) -> OrderResponse:
    use_case = GetOrderUseCase(order_repo)
    order = await use_case.execute(order_id=order_id, current_user=current_user)
    return _order_to_response(order)


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: UUID,
    body: OrderUpdate,
    current_user: User = Depends(require_roles(Role.USER, Role.ADMIN)),
    order_repo: SQLAlchemyOrderRepository = Depends(get_order_repo),
    product_repo: SQLAlchemyProductRepository = Depends(get_product_repo),
    promo_repo: SQLAlchemyPromoCodeRepository = Depends(get_promo_repo),
    user_op_repo: SQLAlchemyUserOperationRepository = Depends(get_user_op_repo),
) -> OrderResponse:
    use_case = UpdateOrderUseCase(order_repo, product_repo, promo_repo, user_op_repo)
    order = await use_case.execute(
        order_id=order_id,
        current_user=current_user,
        new_items=[UpdateOrderItemInput(product_id=i.product_id, quantity=i.quantity) for i in body.items],
    )
    return _order_to_response(order)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    order_repo: SQLAlchemyOrderRepository = Depends(get_order_repo),
) -> OrderResponse:
    use_case = CancelOrderUseCase(order_repo)
    order = await use_case.execute(order_id=order_id, current_user=current_user)
    return _order_to_response(order)
