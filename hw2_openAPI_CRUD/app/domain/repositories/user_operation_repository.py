from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.user_operation import OperationType, UserOperation


class IUserOperationRepository(ABC):
    @abstractmethod
    async def get_last(
        self, user_id: UUID, operation_type: OperationType
    ) -> UserOperation | None: ...

    @abstractmethod
    async def record(
        self, user_id: UUID, operation_type: OperationType
    ) -> UserOperation: ...
