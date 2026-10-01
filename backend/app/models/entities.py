from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
from sqlalchemy import (
    String,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    Numeric,
    JSON,
    DateTime,
)
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.database.connection import Base


def utcnow():
    return datetime.now(timezone.utc)


class Record:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Record, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('EMPLOYEE','MANAGER','ADMIN')"),)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    department: Mapped[str] = mapped_column(String(100))
    manager_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    active: Mapped[bool] = mapped_column(default=True)


class SessionToken(Record, Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(10))
    csrf_token: Mapped[str | None] = mapped_column(String(100))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Project(Record, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str] = mapped_column(String(1000))
    active: Mapped[bool] = mapped_column(default=True)


class Membership(Base):
    __tablename__ = "project_memberships"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)


class Timesheet(Record, Base):
    __tablename__ = "timesheets"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start"),
        CheckConstraint("status IN ('DRAFT','SUBMITTED','APPROVED','REJECTED')"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    week_start: Mapped[date]
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))


class TimeEntry(Record, Base):
    __tablename__ = "time_entries"
    __table_args__ = (CheckConstraint("hours > 0 AND hours <= 24"),)
    timesheet_id: Mapped[UUID] = mapped_column(ForeignKey("timesheets.id"))
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    work_date: Mapped[date]
    hours: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    description: Mapped[str] = mapped_column(String(1000))


class Task(Record, Base):
    __tablename__ = "tasks"
    __table_args__ = (CheckConstraint("status IN ('TODO','IN_PROGRESS','DONE')"),)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="")
    project_id: Mapped[UUID | None] = mapped_column(ForeignKey("projects.id"))
    due_date: Mapped[date | None]
    creator_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    assignee_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20), default="TODO")


class LeaveRequest(Record, Base):
    __tablename__ = "leave_requests"
    __table_args__ = (
        CheckConstraint("end_date >= start_date"),
        CheckConstraint("status IN ('PENDING','APPROVED','REJECTED')"),
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    start_date: Mapped[date]
    end_date: Mapped[date]
    reason: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    reviewer_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(String(1000))


class Ticket(Record, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("priority IN ('LOW','MEDIUM','HIGH')"),
        CheckConstraint("status IN ('OPEN','IN_PROGRESS','RESOLVED','CLOSED')"),
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(2000), default="")
    creator_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM")
    status: Mapped[str] = mapped_column(String(20), default="OPEN")


class AuditEvent(Record, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    source: Mapped[str] = mapped_column(String(10))
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(20))
    request_id: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
