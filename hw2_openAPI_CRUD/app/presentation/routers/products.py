from datetime import timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.application.use_cases.product.create_product import CreateProductUseCase
from app.application.use_cases.product.delete_product import DeleteProductUseCase
from app.application.use_cases.product.get_product import GetProductUseCase
from app.application.use_cases.product.list_products import ListProductsUseCase
from app.application.use_cases.product.update_product import UpdateProductUseCase
from app.domain.entities.product import ProductStatus as DomainProductStatus
from app.domain.entities.user import Role, User
from app.infrastructure.repositories.product_repository import SQLAlchemyProductRepository
from app.presentation.dependencies.auth import get_current_user, require_roles
from app.presentation.dependencies.repositories import get_product_repo
from generated.models import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductStatus,
    ProductUpdate,
)

router = APIRouter(prefix="/products", tags=["products"])


def _product_to_response(product) -> ProductResponse:
    created_at = product.created_at
    updated_at = product.updated_at
    if created_at is not None and created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if updated_at is not None and updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    return ProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        price=product.price,
        stock=product.stock,
        category=product.category,
        status=ProductStatus(product.status),
        seller_id=product.seller_id,
        created_at=created_at,
        updated_at=updated_at,
    )


@router.get("", response_model=ProductListResponse)
async def list_products(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    status: ProductStatus | None = Query(None),
    category: str | None = Query(None),
    _: User = Depends(get_current_user),
    product_repo: SQLAlchemyProductRepository = Depends(get_product_repo),
) -> ProductListResponse:
    domain_status = DomainProductStatus(status) if status else None
    use_case = ListProductsUseCase(product_repo)
    products, total = await use_case.execute(
        page=page, size=size, status=domain_status, category=category
    )
    return ProductListResponse(
        items=[_product_to_response(p) for p in products],
        total_elements=total,
        page=page,
        size=size,
    )


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    body: ProductCreate,
    current_user: User = Depends(require_roles(Role.SELLER, Role.ADMIN)),
    product_repo: SQLAlchemyProductRepository = Depends(get_product_repo),
) -> ProductResponse:
    use_case = CreateProductUseCase(product_repo)
    product = await use_case.execute(
        name=body.name,
        price=body.price,
        stock=body.stock,
        category=body.category,
        status=DomainProductStatus(body.status),
        current_user=current_user,
        description=body.description,
    )
    return _product_to_response(product)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: UUID,
    _: User = Depends(get_current_user),
    product_repo: SQLAlchemyProductRepository = Depends(get_product_repo),
) -> ProductResponse:
    use_case = GetProductUseCase(product_repo)
    product = await use_case.execute(product_id)
    return _product_to_response(product)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: UUID,
    body: ProductUpdate,
    current_user: User = Depends(require_roles(Role.SELLER, Role.ADMIN)),
    product_repo: SQLAlchemyProductRepository = Depends(get_product_repo),
) -> ProductResponse:
    domain_status = DomainProductStatus(body.status) if body.status else None
    use_case = UpdateProductUseCase(product_repo)
    product = await use_case.execute(
        product_id=product_id,
        current_user=current_user,
        name=body.name,
        description=body.description,
        price=body.price,
        stock=body.stock,
        category=body.category,
        status=domain_status,
    )
    return _product_to_response(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    current_user: User = Depends(require_roles(Role.SELLER, Role.ADMIN)),
    product_repo: SQLAlchemyProductRepository = Depends(get_product_repo),
) -> None:
    use_case = DeleteProductUseCase(product_repo)
    await use_case.execute(product_id=product_id, current_user=current_user)
