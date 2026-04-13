from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class OperationType(StrEnum):
    CREATE_ORDER = "CREATE_ORDER"
    UPDATE_ORDER = "UPDATE_ORDER"


@dataclass
class UserOperation:
    id: UUID
    user_id: UUID
    operation_type: OperationType
    created_at: datetime
