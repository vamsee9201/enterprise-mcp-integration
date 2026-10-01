from datetime import date, datetime
from typing import Generic, TypeVar
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class RecordView(BaseModel):
    id: UUID
    created_at: datetime
    model_config = ConfigDict(extra="allow")


class UserView(RecordView):
    name: str
    email: str
    role: str
    department: str
    manager_id: UUID | None
    active: bool


class ProjectView(RecordView):
    name: str
    description: str
    active: bool


class EntryView(RecordView):
    timesheet_id: UUID
    project_id: UUID
    work_date: date
    hours: float
    description: str


class SheetView(BaseModel):
    id: UUID | None
    user_id: UUID
    week_start: date
    status: str
    entries: list[EntryView]
    total_hours: float
    model_config = ConfigDict(extra="allow")


class TaskView(RecordView):
    title: str
    description: str
    assignee_id: UUID
    creator_id: UUID
    project_id: UUID | None
    due_date: date | None
    status: str


class LeaveView(RecordView):
    user_id: UUID
    start_date: date
    end_date: date
    reason: str
    status: str


class TicketView(RecordView):
    title: str
    description: str
    creator_id: UUID
    assignee_id: UUID | None
    priority: str
    status: str


class AuditView(RecordView):
    actor_id: UUID
    source: str
    action: str
    resource_type: str
    resource_id: str | None
    outcome: str
    request_id: str
    details: dict


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
