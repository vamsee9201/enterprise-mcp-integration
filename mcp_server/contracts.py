from typing import Generic, TypeVar
from pydantic import BaseModel
from backend.app.schemas.outputs import ContextView as ContextView


class DeletedView(BaseModel):
    id: str
    status: str


class ReviewView(BaseModel):
    id: str
    kind: str
    user_id: str
    status: str
    user_name: str
    model_config = {"extra": "allow"}


T = TypeVar("T")


class RecordResult(BaseModel, Generic[T]):
    record: T
    request_id: str
    replayed: bool = False


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    request_id: str
