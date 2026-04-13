from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import Role, User
from app.domain.repositories.user_repository import IUserRepository
from app.infrastructure.database.models.user import UserORM


def _to_domain(orm: UserORM) -> User:
    return User(
        id=orm.id,
        username=orm.username,
        email=orm.email,
        hashed_password=orm.hashed_password,
        role=Role(orm.role),
        created_at=orm.created_at,
    )


class SQLAlchemyUserRepository(IUserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.id == user_id)
        )
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.email == email)
        )
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def get_by_username(self, username: str) -> User | None:
        result = await self._session.execute(
            select(UserORM).where(UserORM.username == username)
        )
        orm = result.scalar_one_or_none()
        return _to_domain(orm) if orm else None

    async def create(self, user: User) -> User:
        orm = UserORM(
            id=user.id,
            username=user.username,
            email=user.email,
            hashed_password=user.hashed_password,
            role=user.role,
        )
        self._session.add(orm)
        await self._session.flush()
        await self._session.refresh(orm)
        return _to_domain(orm)
