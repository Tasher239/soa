from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    USER = "USER"
    SELLER = "SELLER"
    ADMIN = "ADMIN"


@dataclass
class User:
    id: UUID
    username: str
    email: str
    hashed_password: str
    role: Role
    created_at: datetime
