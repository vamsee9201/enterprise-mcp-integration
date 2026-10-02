from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal["TODO", "IN_PROGRESS", "DONE"]
TicketStatus = Literal["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]
Priority = Literal["LOW", "MEDIUM", "HIGH"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class TimeEntryInput(Input):
    project_id: UUID
    work_date: date
    hours: Decimal = Field(gt=0, le=24, max_digits=4, decimal_places=2)
    description: str = Field(default="", max_length=1000)


class TaskInput(Input):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    assignee_id: UUID
    project_id: UUID | None = None
    due_date: date | None = None


class TaskEdit(Input):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    project_id: UUID | None = None
    due_date: date | None = None


class LeaveInput(Input):
    start_date: date
    end_date: date
    reason: str = Field(default="", max_length=1000)


class TicketInput(Input):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    priority: Priority = "MEDIUM"


class Rejection(Input):
    reason: str = Field(min_length=1, max_length=1000)


class Assignment(Input):
    assignee_id: UUID


class TaskState(Input):
    status: TaskStatus


class TicketState(Input):
    status: TicketStatus


class TicketPriority(Input):
    priority: Priority


class DemoLogin(Input):
    user_id: UUID


class TaskPatch(Input):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    project_id: UUID | None = None
    due_date: date | None = None

    @classmethod
    def changes(cls, args):
        data = cls(**args)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("Provide at least one task field")
        if any(changes.get(field, "") is None for field in ("title", "description")):
            raise ValueError("Title and description cannot be null")
        return changes
