from datetime import timezone

from fastapi import APIRouter, Depends, status

from app.application.use_cases.auth.login_user import LoginUseCase
from app.application.use_cases.auth.refresh_token import RefreshTokenUseCase
from app.application.use_cases.auth.register_user import RegisterUseCase
from app.domain.entities.user import Role, User
from app.infrastructure.repositories.user_repository import SQLAlchemyUserRepository
from app.presentation.dependencies.repositories import get_user_repo
from generated.models import (
    AccessTokenResponse,
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
    UserRole,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_to_response(user: User) -> UserResponse:
    created_at = user.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        role=UserRole(user.role),
        created_at=created_at,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    user_repo: SQLAlchemyUserRepository = Depends(get_user_repo),
) -> UserResponse:
    use_case = RegisterUseCase(user_repo)
    user = await use_case.execute(
        username=body.username,
        email=str(body.email),
        password=body.password.get_secret_value(),
        role=Role(body.role),
    )
    return _user_to_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    user_repo: SQLAlchemyUserRepository = Depends(get_user_repo),
) -> TokenResponse:
    use_case = LoginUseCase(user_repo)
    token_pair = await use_case.execute(
        email=str(body.email),
        password=body.password.get_secret_value(),
    )
    return TokenResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        token_type=token_pair.token_type,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest,
    user_repo: SQLAlchemyUserRepository = Depends(get_user_repo),
) -> AccessTokenResponse:
    use_case = RefreshTokenUseCase(user_repo)
    result = await use_case.execute(body.refresh_token)
    return AccessTokenResponse(
        access_token=result.access_token,
        token_type=result.token_type,
    )
