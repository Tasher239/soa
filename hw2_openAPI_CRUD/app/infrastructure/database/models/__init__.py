# Import all ORM models so Alembic autogenerate can discover them
from app.infrastructure.database.models.user import UserORM
from app.infrastructure.database.models.product import ProductORM
from app.infrastructure.database.models.promo_code import PromoCodeORM
from app.infrastructure.database.models.order import OrderORM
from app.infrastructure.database.models.order_item import OrderItemORM
from app.infrastructure.database.models.user_operation import UserOperationORM

__all__ = [
    "UserORM",
    "ProductORM",
    "PromoCodeORM",
    "OrderORM",
    "OrderItemORM",
    "UserOperationORM",
]
