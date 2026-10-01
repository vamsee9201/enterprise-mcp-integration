from dataclasses import dataclass
from uuid import UUID
from typing import Literal


@dataclass(frozen=True)
class ActorContext:
    user_id: UUID
    source: Literal["UI", "MCP"]
    request_id: str


class ServiceError(Exception):
    def __init__(self, message: str, code: int = 400):
        self.message = message
        self.code = code
        super().__init__(message)
