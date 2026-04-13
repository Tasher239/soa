from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID


@dataclass
class OrderItem:
    id: UUID
    order_id: UUID
    product_id: UUID
    quantity: int
    price_at_order: Decimal
