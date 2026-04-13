import uuid
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user_operation import OperationType, UserOperation
from app.domain.repositories.user_operation_repository import IUserOperationRepository
from app.infrastructure.database.models.user_operation import UserOperationORM


def _to_domain(orm: UserOperationORM) -> UserOperation:
    return UserOperation(
        id=orm.id,
        user_id=orm.user_id,
        operation_type=OperationType(orm.operation_type),
        created_at=orm.created_at,
    )


class SQLAlchemyUserOperationRepository(IUserOperationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_last(
        self, user_id: UUID, operation_type: OperationType
    ) -> UserOperation | None:
        result = await self._session.execute(
            select(UserOperationORM)
            .where(
                UserOperationORM.user_id == user_id,
                UserOperationORM.operation_type == operation_type,
            )
            .order_by(desc(UserOperationORM.created_at))
            .limit(1)
        )
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def record(
        self, user_id: UUID, operation_type: OperationType
    ) -> UserOperation:
        orm = UserOperationORM(
            id=uuid.uuid4(),
            user_id=user_id,
            operation_type=operation_type,
        )
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return _to_domain(orm)
