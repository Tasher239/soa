from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.promo_code import PromoCode


class IPromoCodeRepository(ABC):
    @abstractmethod
    async def get_by_code(self, code: str) -> PromoCode | None: ...

    @abstractmethod
    async def create(self, promo: PromoCode) -> PromoCode: ...

    @abstractmethod
    async def increment_uses(self, promo_id: UUID) -> None: ...

    @abstractmethod
    async def decrement_uses(self, promo_id: UUID) -> None: ...

    @abstractmethod
    async def get_code_by_id(self, promo_id: UUID) -> str | None:
        ...
