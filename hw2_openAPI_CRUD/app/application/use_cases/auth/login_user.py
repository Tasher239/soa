from dataclasses import dataclass

from app.domain.exceptions import TokenInvalidException
from app.domain.repositories.user_repository import IUserRepository
from app.infrastructure.security.jwt_service import jwt_service
from app.infrastructure.security.password_service import verify_password


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginUseCase:
    def __init__(self, user_repo: IUserRepository) -> None:
        self._repo = user_repo

    async def execute(self, email: str, password: str) -> TokenPair:
        user = await self._repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise TokenInvalidException("Invalid email or password")

        access_token = jwt_service.create_access_token(str(user.id), user.role)
        refresh_token = jwt_service.create_refresh_token(str(user.id))

        return TokenPair(access_token=access_token, refresh_token=refresh_token)
