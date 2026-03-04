from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.domain.entities.user import Role, User
from app.domain.exceptions import AccessDeniedException, TokenInvalidException
from app.domain.repositories.user_repository import IUserRepository
from app.infrastructure.security.jwt_service import jwt_service
from app.presentation.dependencies.repositories import get_user_repo

_bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    user_repo: IUserRepository = Depends(get_user_repo),
) -> User:
    payload = jwt_service.decode_access_token(credentials.credentials)
    user_id = UUID(payload["sub"])
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise TokenInvalidException("User not found")
    return user


def require_roles(*roles: Role):
    async def _check(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in roles:
            raise AccessDeniedException(
                f"Role {current_user.role} not allowed. "
                f"Required: {', '.join(roles)}"
            )
        return current_user

    return _check
