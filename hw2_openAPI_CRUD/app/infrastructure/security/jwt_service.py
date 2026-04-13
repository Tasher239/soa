from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError

from app.core.config import settings
from app.domain.exceptions import (
    RefreshTokenInvalidException,
    TokenExpiredException,
    TokenInvalidException,
)


class JWTService:
    def __init__(self) -> None:
        self._secret = settings.jwt_secret
        self._algorithm = settings.jwt_algorithm

    def create_access_token(self, user_id: str, role: str) -> str:
        payload = {
            "sub": user_id,
            "role": role,
            "type": "access",
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=settings.access_token_expire_minutes),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def create_refresh_token(self, user_id: str) -> str:
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": datetime.now(timezone.utc)
            + timedelta(days=settings.refresh_token_expire_days),
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)

    def decode_access_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
            if payload.get("type") != "access":
                raise TokenInvalidException("Not an access token")
            return payload
        except ExpiredSignatureError:
            raise TokenExpiredException("Access token has expired")
        except JWTError:
            raise TokenInvalidException("Invalid access token")

    def decode_refresh_token(self, token: str) -> dict:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
            if payload.get("type") != "refresh":
                raise RefreshTokenInvalidException("Not a refresh token")
            return payload
        except ExpiredSignatureError:
            raise RefreshTokenInvalidException("Refresh token has expired")
        except JWTError:
            raise RefreshTokenInvalidException("Invalid refresh token")


jwt_service = JWTService()
