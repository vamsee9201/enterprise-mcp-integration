"""Application rules shared by HTTP and MCP. No transport dependencies."""

import hashlib
import json
from uuid import UUID
from zoneinfo import ZoneInfo
from backend.app.config import settings
from datetime import date, timedelta, datetime, timezone
from decimal import Decimal
from sqlalchemy import select, func, or_
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError
from fastapi.encoders import jsonable_encoder
from backend.app.database.connection import SessionLocal
from backend.app.auth.context import ActorContext, ServiceError
from backend.app.models.entities import (
    User,
    Project,
    Membership,
    Timesheet,
    TimeEntry,
    Task,
    LeaveRequest,
    Ticket,
    AuditEvent,
    utcnow,
    IdempotencyRecord,
)
from backend.app.schemas.inputs import (
    TimeEntryInput,
    TaskInput,
    TaskEdit,
    TaskPatch,
    LeaveInput,
    TicketInput,
    Rejection,
)

OPERATIONS: dict[str, str | None] = {}


def operation(resource=None):
    def decorate(fn):
        OPERATIONS[fn.__name__] = resource
        return fn

    return decorate


def monday(value: date):
    return value - timedelta(days=value.weekday())


def run(actor: ActorContext, operation_name: str, *, idempotency_key=None, **args):
    """One transaction per business operation, with atomic success audits.

    Actor locks serialize a user's entry totals / leave overlap checks in PostgreSQL.
    Resource locks serialize review decisions. The identity and role are reloaded.
    """
    if operation_name not in OPERATIONS:
        raise ServiceError("Unknown operation", 404)
    resource = OPERATIONS[operation_name]
    with SessionLocal() as db:
        try:
            query = select(User).where(User.id == actor.user_id, User.active.is_(True))
            if resource:
                query = query.with_for_update()
            user = db.scalar(query)
            if not user:
                raise ServiceError("Account unavailable", 401)
            service = Portal(db, user, bool(resource))
            fingerprint = None
            if idempotency_key is not None:
                models = {
                    "add_time_entry": TimeEntryInput,
                    "create_task": TaskInput,
                    "request_leave": LeaveInput,
                    "create_ticket": TicketInput,
                }
                if operation_name not in models:
                    raise ServiceError("Retry keys are supported only for creation operations", 422)
                normalized = models[operation_name](**args).model_dump(mode="json")
                if "hours" in normalized:
                    normalized["hours"] = str(Decimal(normalized["hours"]).normalize())
                fingerprint = hashlib.sha256(
                    json.dumps(normalized, sort_keys=True).encode()
                ).hexdigest()
                saved = db.scalar(
                    select(IdempotencyRecord).where(
                        IdempotencyRecord.actor_id == user.id,
                        IdempotencyRecord.operation == operation_name,
                        IdempotencyRecord.key == idempotency_key,
                    )
                )
                if saved:
                    if saved.fingerprint != fingerprint:
                        raise ServiceError("Idempotency key reused with different arguments", 409)
                    record = saved.result
                    if operation_name == "add_time_entry":
                        service.get_timesheet(UUID(record["timesheet_id"]))
                    else:
                        reader = {
                            "create_task": "get_task",
                            "request_leave": "get_leave_request",
                            "create_ticket": "get_ticket",
                        }[operation_name]
                        getattr(service, reader)(UUID(record["id"]))
                    return {**record, "replayed": True}
            result = getattr(service, operation_name)(**args)
            if fingerprint is not None:
                db.add(
                    IdempotencyRecord(
                        actor_id=user.id,
                        operation=operation_name,
                        key=idempotency_key,
                        fingerprint=fingerprint,
                        result=result,
                    )
                )
                result = {**result, "replayed": False}
            if resource:
                db.add(
                    AuditEvent(
                        actor_id=user.id,
                        source=actor.source,
                        action=operation_name,
                        resource_type=resource,
                        resource_id=str(result.get("id") or ""),
                        outcome="SUCCESS",
                        request_id=actor.request_id,
                        details={"status": result.get("status")},
                    )
                )
            db.commit()
            return result
        except (ServiceError, ValidationError, IntegrityError) as exc:
            db.rollback()
            if isinstance(exc, ValidationError):
                error = ServiceError(
                    "Invalid input: " + "; ".join(e["msg"] for e in exc.errors()), 422
                )
            elif isinstance(exc, IntegrityError):
                error = ServiceError("Record changed concurrently; refresh and retry", 409)
            else:
                error = exc
            if resource and db.get(User, actor.user_id):
                db.add(
                    AuditEvent(
                        actor_id=actor.user_id,
                        source=actor.source,
                        action=operation_name,
                        resource_type=resource,
                        resource_id=str(
                            args.get("timesheet_id")
                            or args.get("entry_id")
                            or args.get("task_id")
                            or args.get("leave_id")
                            or args.get("ticket_id")
                            or ""
                        ),
                        outcome="DENIED" if error.code == 403 else "FAILED",
                        request_id=actor.request_id,
                        details={"error": error.message},
                    )
                )
                db.commit()
            raise error from exc


class Portal:
    def __init__(self, db, user, writing=False):
        self.db, self.user, self.writing = db, user, writing

    def _load(self, model, record_id):
        query = select(model).where(model.id == record_id)
        if self.writing and model in (Timesheet, TimeEntry, Task, LeaveRequest, Ticket):
            query = query.with_for_update()
        obj = self.db.scalar(query)
        if not obj:
            raise ServiceError("Record not found", 404)
        return obj

    def _team_ids(self):
        if self.user.role == "ADMIN":
            return list(self.db.scalars(select(User.id)))
        return (
            [self.user.id, *self.db.scalars(select(User.id).where(User.manager_id == self.user.id))]
            if self.user.role == "MANAGER"
            else [self.user.id]
        )

    def _person(self, user_id):
        if user_id not in self._team_ids():
            raise ServiceError("You cannot access this employee’s records", 403)

    def _review(self, user_id):
        if user_id == self.user.id:
            raise ServiceError("You cannot approve or reject your own request", 403)
        if self.user.role not in ("MANAGER", "ADMIN"):
            raise ServiceError("Manager permission required", 403)
        self._person(user_id)

    def _manager(self):
        if self.user.role not in ("MANAGER", "ADMIN"):
            raise ServiceError("Manager permission required", 403)

    def _dump(self, obj):
        values = {column.name: getattr(obj, column.name) for column in obj.__table__.columns}
        values = {
            key: value.replace(tzinfo=timezone.utc)
            if isinstance(value, datetime) and value.tzinfo is None
            else value
            for key, value in values.items()
        }
        data = jsonable_encoder(values)
        for field in (
            "user_id",
            "creator_id",
            "assignee_id",
            "reviewer_id",
            "actor_id",
            "manager_id",
        ):
            uid = getattr(obj, field, None)
            if uid:
                person = self.db.get(User, uid)
                data[field.replace("_id", "_name")] = person.name if person else None
        pid = getattr(obj, "project_id", None)
        if pid:
            data["project_name"] = self.db.get(Project, pid).name
        if isinstance(obj, Timesheet):
            entries = list(
                self.db.scalars(
                    select(TimeEntry)
                    .where(TimeEntry.timesheet_id == obj.id)
                    .order_by(TimeEntry.work_date, TimeEntry.created_at)
                )
            )
            data["entries"] = [self._dump(entry) for entry in entries]
            data["total_hours"] = float(sum((entry.hours for entry in entries), Decimal(0)))
        return data

    def _page(self, query, limit=50, offset=0):
        if not 1 <= limit <= 100 or offset < 0:
            raise ServiceError("Limit must be 1–100 and offset nonnegative", 422)
        count = self.db.scalar(select(func.count()).select_from(query.subquery()))
        return {
            "items": [
                self._dump(obj) for obj in self.db.scalars(query.limit(limit).offset(offset))
            ],
            "total": count,
            "limit": limit,
            "offset": offset,
        }

    @operation()
    def get_me(self):
        return self._dump(self.user)

    @operation()
    def get_my_context(self):
        current = utcnow().astimezone(ZoneInfo(settings.app_timezone)).date()
        return {
            "user": self._dump(self.user),
            "manager": self._dump(self.db.get(User, self.user.manager_id))
            if self.user.manager_id
            else None,
            "timezone": settings.app_timezone,
            "today": current.isoformat(),
            "week_start": monday(current).isoformat(),
        }

    @operation()
    def list_timesheets(
        self, employee_id=None, start_week=None, end_week=None, status=None, limit=50, offset=0
    ):
        if status and status not in ("DRAFT", "SUBMITTED", "APPROVED", "REJECTED"):
            raise ServiceError("Invalid timesheet status", 422)
        if start_week and end_week and start_week > end_week:
            raise ServiceError("Invalid week range", 422)
        q = select(Timesheet).where(Timesheet.user_id.in_(self._team_ids()))
        if employee_id:
            self._person(employee_id)
            q = q.where(Timesheet.user_id == employee_id)
        if start_week:
            q = q.where(Timesheet.week_start >= monday(start_week))
        if end_week:
            q = q.where(Timesheet.week_start <= monday(end_week))
        if status:
            q = q.where(Timesheet.status == status)
        return self._page(q.order_by(Timesheet.week_start.desc(), Timesheet.id), limit, offset)

    @operation()
    def search_employees(self, query="", department=None, manager_id=None, limit=50, offset=0):
        q = select(User).where(User.active.is_(True))
        if query:
            manager_ids = select(User.id).where(User.name.ilike(f"%{query}%"))
            q = q.where(
                or_(
                    User.name.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%"),
                    User.department.ilike(f"%{query}%"),
                    User.manager_id.in_(manager_ids),
                )
            )
        if department:
            q = q.where(User.department == department)
        if manager_id:
            q = q.where(User.manager_id == manager_id)
        return self._page(q.order_by(User.name), limit, offset)

    @operation()
    def get_employee(self, employee_id):
        return self._dump(self._load(User, employee_id))

    @operation()
    def list_projects(self, query="", limit=50, offset=0):
        q = select(Project).where(Project.active.is_(True), Project.name.ilike(f"%{query}%"))
        if self.user.role != "ADMIN":
            q = q.where(
                Project.id.in_(
                    select(Membership.project_id).where(Membership.user_id == self.user.id)
                )
            )
        return self._page(q.order_by(Project.name), limit, offset)

    @operation()
    def get_project(self, project_id):
        project = self._load(Project, project_id)
        if self.user.role != "ADMIN" and not self.db.get(Membership, (project_id, self.user.id)):
            raise ServiceError("Project membership required", 403)
        return self._dump(project)

    @operation()
    def get_my_timesheet(self, week):
        week = monday(week)
        sheet = self.db.scalar(
            select(Timesheet).where(Timesheet.user_id == self.user.id, Timesheet.week_start == week)
        )
        return (
            self._dump(sheet)
            if sheet
            else {
                "id": None,
                "user_id": str(self.user.id),
                "week_start": week.isoformat(),
                "status": "DRAFT",
                "entries": [],
                "total_hours": 0,
            }
        )

    @operation()
    def get_timesheet(self, timesheet_id):
        sheet = self._load(Timesheet, timesheet_id)
        self._person(sheet.user_id)
        return self._dump(sheet)

    def _draft(self, sheet):
        if sheet.user_id != self.user.id:
            raise ServiceError("Only the owner can edit a timesheet", 403)
        if sheet.status not in ("DRAFT", "REJECTED"):
            raise ServiceError("Submitted and approved timesheets are locked", 409)
        sheet.status = "DRAFT"
        sheet.reviewer_id = sheet.reviewed_at = sheet.rejection_reason = sheet.submitted_at = None

    def _validate_entry(self, sheet, data, excluding=None):
        if monday(data.work_date) != sheet.week_start:
            raise ServiceError("Entry date must be within the timesheet week", 422)
        project = self._load(Project, data.project_id)
        if not project.active or not self.db.get(Membership, (project.id, self.user.id)):
            raise ServiceError("An active assigned project is required", 403)
        q = select(func.coalesce(func.sum(TimeEntry.hours), 0)).where(
            TimeEntry.timesheet_id == sheet.id, TimeEntry.work_date == data.work_date
        )
        if excluding:
            q = q.where(TimeEntry.id != excluding)
        if self.db.scalar(q) + data.hours > 24:
            raise ServiceError("Daily hours cannot exceed 24", 422)

    @operation("time_entry")
    def add_time_entry(self, **args):
        data = TimeEntryInput(**args)
        week = monday(data.work_date)
        sheet = self.db.scalar(
            select(Timesheet)
            .where(Timesheet.user_id == self.user.id, Timesheet.week_start == week)
            .with_for_update()
        )
        if not sheet:
            sheet = Timesheet(user_id=self.user.id, week_start=week)
            self.db.add(sheet)
            self.db.flush()
        self._draft(sheet)
        self._validate_entry(sheet, data)
        entry = TimeEntry(timesheet_id=sheet.id, **data.model_dump())
        self.db.add(entry)
        self.db.flush()
        return self._dump(entry)

    @operation("time_entry")
    def update_time_entry(self, entry_id, **args):
        data = TimeEntryInput(**args)
        entry = self._load(TimeEntry, entry_id)
        sheet = self._load(Timesheet, entry.timesheet_id)
        self._draft(sheet)
        self._validate_entry(sheet, data, entry.id)
        for key, value in data.model_dump().items():
            setattr(entry, key, value)
        self.db.flush()
        return self._dump(entry)

    @operation("time_entry")
    def delete_time_entry(self, entry_id):
        entry = self._load(TimeEntry, entry_id)
        self._draft(self._load(Timesheet, entry.timesheet_id))
        result = {"id": str(entry.id), "status": "DELETED"}
        self.db.delete(entry)
        return result

    @operation("timesheet")
    def submit_timesheet(self, week):
        sheet = self.db.scalar(
            select(Timesheet)
            .where(Timesheet.user_id == self.user.id, Timesheet.week_start == monday(week))
            .with_for_update()
        )
        if not sheet:
            raise ServiceError("Add at least one entry before submitting", 422)
        self._draft(sheet)
        if not self.db.scalar(
            select(func.count()).select_from(TimeEntry).where(TimeEntry.timesheet_id == sheet.id)
        ):
            raise ServiceError("Add at least one entry before submitting", 422)
        sheet.status, sheet.submitted_at = "SUBMITTED", utcnow()
        self.db.flush()
        return self._dump(sheet)

    def _decision(self, model, record_id, approved, reason):
        obj = self._load(model, record_id)
        self._review(obj.user_id)
        pending = "SUBMITTED" if model == Timesheet else "PENDING"
        if obj.status != pending:
            raise ServiceError("This request has already been reviewed or is not submitted", 409)
        if not approved:
            reason = Rejection(reason=reason).reason
        obj.status = "APPROVED" if approved else "REJECTED"
        obj.reviewer_id, obj.reviewed_at = self.user.id, utcnow()
        obj.rejection_reason = None if approved else reason
        self.db.flush()
        return self._dump(obj)

    @operation("timesheet")
    def approve_timesheet(self, timesheet_id):
        return self._decision(Timesheet, timesheet_id, True, None)

    @operation("timesheet")
    def reject_timesheet(self, timesheet_id, reason):
        return self._decision(Timesheet, timesheet_id, False, reason)

    @operation()
    def list_tasks(self, query="", status=None, assignee_id=None, limit=50, offset=0):
        q = select(Task).where(
            Task.assignee_id.in_(self._team_ids()), Task.title.ilike(f"%{query}%")
        )
        if status:
            q = q.where(Task.status == status)
        if assignee_id:
            q = q.where(Task.assignee_id == assignee_id)
        return self._page(q.order_by(Task.created_at.desc()), limit, offset)

    @operation()
    def get_task(self, task_id):
        task = self._load(Task, task_id)
        self._person(task.assignee_id)
        return self._dump(task)

    def _assignee(self, assignee_id):
        self._person(assignee_id)
        user = self._load(User, assignee_id)
        if not user.active:
            raise ServiceError("Assignee is inactive", 422)

    def _task_project(self, project_id):
        if project_id:
            project = self._load(Project, project_id)
            if not project.active:
                raise ServiceError("Project is inactive", 422)
            if self.user.role != "ADMIN" and not self.db.get(
                Membership, (project_id, self.user.id)
            ):
                raise ServiceError("Project membership required", 403)

    @operation("task")
    def create_task(self, **args):
        self._manager()
        data = TaskInput(**args)
        self._assignee(data.assignee_id)
        self._task_project(data.project_id)
        task = Task(creator_id=self.user.id, **data.model_dump())
        self.db.add(task)
        self.db.flush()
        return self._dump(task)

    @operation("task")
    def update_task(self, task_id, **args):
        self._manager()
        task = self._load(Task, task_id)
        self._person(task.assignee_id)
        data = TaskEdit(**args)
        self._task_project(data.project_id)
        for key, value in data.model_dump().items():
            setattr(task, key, value)
        return self._dump(task)

    @operation("task")
    def patch_task(self, task_id, **args):
        self._manager()
        task = self._load(Task, task_id)
        self._person(task.assignee_id)
        try:
            changes = TaskPatch.changes(args)
        except ValidationError:
            raise
        except ValueError as exc:
            raise ServiceError(str(exc), 422) from exc
        if "project_id" in changes:
            self._task_project(changes["project_id"])
        for field, value in changes.items():
            setattr(task, field, value)
        return self._dump(task)

    @operation("task")
    def assign_task(self, task_id, assignee_id):
        self._manager()
        task = self._load(Task, task_id)
        self._person(task.assignee_id)
        self._assignee(assignee_id)
        task.assignee_id = assignee_id
        return self._dump(task)

    @operation("task")
    def update_task_status(self, task_id, status):
        task = self._load(Task, task_id)
        self._person(task.assignee_id)
        if status not in ("TODO", "IN_PROGRESS", "DONE"):
            raise ServiceError("Invalid task status", 422)
        task.status = status
        return self._dump(task)

    @operation()
    def list_leave_requests(self, status=None, limit=50, offset=0):
        q = select(LeaveRequest).where(LeaveRequest.user_id.in_(self._team_ids()))
        if status:
            q = q.where(LeaveRequest.status == status)
        return self._page(q.order_by(LeaveRequest.created_at.desc()), limit, offset)

    @operation()
    def get_leave_request(self, leave_id):
        leave = self._load(LeaveRequest, leave_id)
        self._person(leave.user_id)
        return self._dump(leave)

    @operation("leave_request")
    def request_leave(self, **args):
        data = LeaveInput(**args)
        if data.end_date < data.start_date:
            raise ServiceError("End date must be on or after start date", 422)
        overlap = self.db.scalar(
            select(LeaveRequest).where(
                LeaveRequest.user_id == self.user.id,
                LeaveRequest.status.in_(["PENDING", "APPROVED"]),
                LeaveRequest.start_date <= data.end_date,
                LeaveRequest.end_date >= data.start_date,
            )
        )
        if overlap:
            raise ServiceError("Dates overlap a pending or approved leave request", 409)
        leave = LeaveRequest(user_id=self.user.id, **data.model_dump())
        self.db.add(leave)
        self.db.flush()
        return self._dump(leave)

    @operation("leave_request")
    def approve_leave(self, leave_id):
        return self._decision(LeaveRequest, leave_id, True, None)

    @operation("leave_request")
    def reject_leave(self, leave_id, reason):
        return self._decision(LeaveRequest, leave_id, False, reason)

    @operation()
    def list_tickets(
        self, query="", status=None, priority=None, assignee_id=None, limit=50, offset=0
    ):
        q = select(Ticket).where(Ticket.title.ilike(f"%{query}%"))
        if self.user.role == "EMPLOYEE":
            q = q.where(or_(Ticket.creator_id == self.user.id, Ticket.assignee_id == self.user.id))
        if status:
            q = q.where(Ticket.status == status)
        if priority:
            q = q.where(Ticket.priority == priority)
        if assignee_id:
            q = q.where(Ticket.assignee_id == assignee_id)
        return self._page(q.order_by(Ticket.created_at.desc()), limit, offset)

    def _ticket(self, ticket_id):
        ticket = self._load(Ticket, ticket_id)
        if self.user.role == "EMPLOYEE" and self.user.id not in (
            ticket.creator_id,
            ticket.assignee_id,
        ):
            raise ServiceError("You can access only tickets you created or are assigned to", 403)
        return ticket

    @operation()
    def get_ticket(self, ticket_id):
        return self._dump(self._ticket(ticket_id))

    @operation("ticket")
    def create_ticket(self, **args):
        ticket = Ticket(creator_id=self.user.id, **TicketInput(**args).model_dump())
        self.db.add(ticket)
        self.db.flush()
        return self._dump(ticket)

    @operation("ticket")
    def assign_ticket(self, ticket_id, assignee_id):
        self._manager()
        ticket = self._ticket(ticket_id)
        user = self._load(User, assignee_id)
        if not user.active:
            raise ServiceError("Assignee is inactive", 422)
        ticket.assignee_id = assignee_id
        return self._dump(ticket)

    @operation("ticket")
    def update_ticket_priority(self, ticket_id, priority):
        self._manager()
        ticket = self._ticket(ticket_id)
        if priority not in ("LOW", "MEDIUM", "HIGH"):
            raise ServiceError("Invalid priority", 422)
        ticket.priority = priority
        return self._dump(ticket)

    @operation("ticket")
    def update_ticket_status(self, ticket_id, status):
        ticket = self._ticket(ticket_id)
        if status not in ("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"):
            raise ServiceError("Invalid ticket status", 422)
        ticket.status = status
        return self._dump(ticket)

    @operation()
    def list_pending_approvals(self, kind=None, limit=50, offset=0):
        self._manager()
        ids = [uid for uid in self._team_ids() if uid != self.user.id]
        items = []
        for model, pending, label in [
            (Timesheet, "SUBMITTED", "timesheet"),
            (LeaveRequest, "PENDING", "leave"),
        ]:
            if kind and kind != label:
                continue
            for obj in self.db.scalars(
                select(model).where(model.user_id.in_(ids), model.status == pending)
            ):
                items.append({**self._dump(obj), "kind": label})
        items.sort(key=lambda x: x["submitted_at"] if x["kind"] == "timesheet" else x["created_at"])
        if not 1 <= limit <= 100 or offset < 0:
            raise ServiceError("Invalid pagination", 422)
        return {
            "items": items[offset : offset + limit],
            "total": len(items),
            "limit": limit,
            "offset": offset,
        }

    @operation()
    def get_recent_activity(
        self,
        actor_id=None,
        source=None,
        action=None,
        resource_type=None,
        outcome=None,
        start_date=None,
        end_date=None,
        limit=50,
        offset=0,
    ):
        q = select(AuditEvent).where(AuditEvent.actor_id.in_(self._team_ids()))
        for field, value in [
            ("actor_id", actor_id),
            ("source", source),
            ("action", action),
            ("resource_type", resource_type),
            ("outcome", outcome),
        ]:
            if value:
                q = q.where(getattr(AuditEvent, field) == value)
        # Treat filter dates as calendar days in the configured application timezone.
        from datetime import datetime, time
        from zoneinfo import ZoneInfo
        from backend.app.config import settings

        zone = ZoneInfo(settings.app_timezone)
        if start_date:
            q = q.where(
                AuditEvent.created_at
                >= datetime.combine(start_date, time.min, zone).astimezone(timezone.utc)
            )
        if end_date:
            q = q.where(
                AuditEvent.created_at
                < datetime.combine(end_date + timedelta(days=1), time.min, zone).astimezone(
                    timezone.utc
                )
            )
        return self._page(q.order_by(AuditEvent.created_at.desc(), AuditEvent.id), limit, offset)
