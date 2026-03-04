from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class DiscountType(StrEnum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


@dataclass
class PromoCode:
    id: UUID
    code: str
    discount_type: DiscountType
    discount_value: Decimal
    min_order_amount: Decimal
    max_uses: int
    current_uses: int
    valid_from: datetime
    valid_until: datetime
    active: bool

    def is_usable(self, now: datetime) -> bool:
        return (
            self.active
            and self.current_uses < self.max_uses
            and self.valid_from <= now <= self.valid_until
        )
