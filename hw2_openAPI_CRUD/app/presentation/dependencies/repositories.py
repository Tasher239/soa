from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.session import get_db
from app.infrastructure.repositories.order_repository import SQLAlchemyOrderRepository
from app.infrastructure.repositories.product_repository import SQLAlchemyProductRepository
from app.infrastructure.repositories.promo_code_repository import SQLAlchemyPromoCodeRepository
from app.infrastructure.repositories.user_operation_repository import SQLAlchemyUserOperationRepository
from app.infrastructure.repositories.user_repository import SQLAlchemyUserRepository


def get_user_repo(session: AsyncSession = Depends(get_db)) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(session)


def get_product_repo(session: AsyncSession = Depends(get_db)) -> SQLAlchemyProductRepository:
    return SQLAlchemyProductRepository(session)


def get_order_repo(session: AsyncSession = Depends(get_db)) -> SQLAlchemyOrderRepository:
    return SQLAlchemyOrderRepository(session)


def get_promo_repo(session: AsyncSession = Depends(get_db)) -> SQLAlchemyPromoCodeRepository:
    return SQLAlchemyPromoCodeRepository(session)


def get_user_op_repo(session: AsyncSession = Depends(get_db)) -> SQLAlchemyUserOperationRepository:
    return SQLAlchemyUserOperationRepository(session)
