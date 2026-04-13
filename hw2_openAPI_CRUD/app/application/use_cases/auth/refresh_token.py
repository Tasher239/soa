from dataclasses import dataclass
from uuid import UUID

from app.domain.exceptions import RefreshTokenInvalidException, TokenInvalidException
from app.domain.repositories.user_repository import IUserRepository
from app.infrastructure.security.jwt_service import jwt_service


@dataclass
class AccessTokenResult:
    access_token: str
    token_type: str = "bearer"


class RefreshTokenUseCase:
    def __init__(self, user_repo: IUserRepository) -> None:
        self._repo = user_repo

    async def execute(self, refresh_token: str) -> AccessTokenResult:
        payload = jwt_service.decode_refresh_token(refresh_token)
        user_id = UUID(payload["sub"])

        user = await self._repo.get_by_id(user_id)
        if not user:
            raise RefreshTokenInvalidException("User not found")

        access_token = jwt_service.create_access_token(str(user.id), user.role)
        return AccessTokenResult(access_token=access_token)
