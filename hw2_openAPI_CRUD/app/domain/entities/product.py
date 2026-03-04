from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class ProductStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


@dataclass
class Product:
    id: UUID
    name: str
    price: Decimal
    stock: int
    category: str
    status: ProductStatus
    seller_id: UUID
    created_at: datetime
    updated_at: datetime
    description: str | None = None
