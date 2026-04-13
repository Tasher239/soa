import uuid

from app.domain.entities.user import Role, User
from app.domain.exceptions import ConflictException, TokenInvalidException
from app.domain.repositories.user_repository import IUserRepository
from app.infrastructure.security.password_service import hash_password


class RegisterUseCase:
    def __init__(self, user_repo: IUserRepository) -> None:
        self._repo = user_repo

    async def execute(
        self,
        username: str,
        email: str,
        password: str,
        role: Role,
    ) -> User:
        if await self._repo.get_by_email(email):
            raise ConflictException("Email already registered")
        if await self._repo.get_by_username(username):
            raise ConflictException("Username already taken")

        user = User(
            id=uuid.uuid4(),
            username=username,
            email=email,
            hashed_password=hash_password(password),
            role=role,
            created_at=None,  # type: ignore[arg-type]
        )
        return await self._repo.create(user)
