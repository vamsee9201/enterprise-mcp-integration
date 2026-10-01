import secrets
from datetime import date
from typing import Annotated, Literal
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, Request, Response, Query
from sqlalchemy import select
from backend.app.config import settings
from backend.app.auth.context import ActorContext, ServiceError
from backend.app.auth.tokens import issue_token, resolve_token, revoke_token
from backend.app.database.connection import SessionLocal
from backend.app.models.entities import User
from backend.app.services.portal import run
from backend.app.schemas.inputs import (
    Assignment,
    DemoLogin,
    LeaveInput,
    Priority,
    Rejection,
    TaskEdit,
    TaskInput,
    TaskState,
    TaskStatus,
    TicketInput,
    TicketPriority,
    TicketState,
    TicketStatus,
    TimeEntryInput,
)
from backend.app.schemas.outputs import (
    AuditView,
    EntryView,
    LeaveView,
    Page,
    ProjectView,
    SheetView,
    TaskView,
    TicketView,
    UserView,
)

router = APIRouter(prefix="/api/v1")
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def actor(request: Request):
    session = resolve_token(request.cookies.get("portal_session", ""))
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(csrf, session.csrf_token or ""):
            raise ServiceError("Invalid CSRF token", 403)
        if request.headers.get("origin") != settings.web_origin:
            raise ServiceError("Invalid request origin", 403)
    return ActorContext(session.user_id, "UI", str(uuid4()))


Actor = Annotated[ActorContext, Depends(actor)]


@router.get("/auth/demo-accounts", response_model=list[UserView])
def demo_accounts():
    if not settings.demo_mode:
        raise ServiceError("Demo login is disabled", 404)
    with SessionLocal() as db:
        from backend.app.services.portal import Portal

        return [
            Portal(db, user)._dump(user)
            for user in db.scalars(select(User).where(User.active.is_(True)).order_by(User.name))
        ]


@router.post("/auth/demo-login")
def demo_login(body: DemoLogin, request: Request, response: Response):
    if not settings.demo_mode:
        raise ServiceError("Demo login is disabled", 404)
    if request.headers.get("origin") != settings.web_origin:
        raise ServiceError("Invalid request origin", 403)
    # Seed CLI owns the demo account allowlist; arbitrary created accounts cannot log in.
    from backend.app.database.seed import USERS

    if body.user_id not in {u["id"] for u in USERS}:
        raise ServiceError("Not a demo account", 403)
    old = request.cookies.get("portal_session")
    if old:
        revoke_token(old)
    token, csrf = issue_token(body.user_id)
    response.set_cookie(
        "portal_session",
        token,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        max_age=28800,
        path="/",
    )
    return {
        "user": run(ActorContext(body.user_id, "UI", str(uuid4())), "get_me"),
        "csrf_token": csrf,
    }


@router.get("/auth/me")
def me(a: Actor, request: Request):
    return {
        "user": run(a, "get_me"),
        "csrf_token": resolve_token(request.cookies["portal_session"]).csrf_token,
    }


@router.post("/auth/logout")
def logout(a: Actor, request: Request, response: Response):
    revoke_token(request.cookies["portal_session"])
    response.delete_cookie("portal_session", path="/")
    return {"ok": True}


@router.get("/employees", response_model=Page[UserView])
def employees(
    a: Actor,
    query: str = "",
    department: str | None = None,
    manager_id: UUID | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return run(
        a,
        "search_employees",
        query=query,
        department=department,
        manager_id=manager_id,
        limit=limit,
        offset=offset,
    )


@router.get("/employees/{employee_id}", response_model=UserView)
def employee(employee_id: UUID, a: Actor):
    return run(a, "get_employee", employee_id=employee_id)


@router.get("/projects", response_model=Page[ProjectView])
def projects(a: Actor, query: str = "", limit: Limit = 50, offset: Offset = 0):
    return run(a, "list_projects", query=query, limit=limit, offset=offset)


@router.get("/projects/{project_id}", response_model=ProjectView)
def project(project_id: UUID, a: Actor):
    return run(a, "get_project", project_id=project_id)


@router.get("/timesheets/me", response_model=SheetView)
def own_timesheet(week: date, a: Actor):
    return run(a, "get_my_timesheet", week=week)


@router.get("/timesheets/{timesheet_id}", response_model=SheetView)
def timesheet(timesheet_id: UUID, a: Actor):
    return run(a, "get_timesheet", timesheet_id=timesheet_id)


@router.post("/time-entries", response_model=EntryView)
def add_entry(body: TimeEntryInput, a: Actor):
    return run(a, "add_time_entry", **body.model_dump())


@router.put("/time-entries/{entry_id}", response_model=EntryView)
def update_entry(entry_id: UUID, body: TimeEntryInput, a: Actor):
    return run(a, "update_time_entry", entry_id=entry_id, **body.model_dump())


@router.delete("/time-entries/{entry_id}")
def delete_entry(entry_id: UUID, a: Actor):
    return run(a, "delete_time_entry", entry_id=entry_id)


@router.post("/timesheets/submit", response_model=SheetView)
def submit(week: date, a: Actor):
    return run(a, "submit_timesheet", week=week)


@router.post("/timesheets/{timesheet_id}/approve", response_model=SheetView)
def approve_sheet(timesheet_id: UUID, a: Actor):
    return run(a, "approve_timesheet", timesheet_id=timesheet_id)


@router.post("/timesheets/{timesheet_id}/reject", response_model=SheetView)
def reject_sheet(timesheet_id: UUID, body: Rejection, a: Actor):
    return run(a, "reject_timesheet", timesheet_id=timesheet_id, reason=body.reason)


@router.get("/tasks", response_model=Page[TaskView])
def tasks(
    a: Actor,
    query: str = "",
    status: TaskStatus | None = None,
    assignee_id: UUID | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return run(
        a,
        "list_tasks",
        query=query,
        status=status,
        assignee_id=assignee_id,
        limit=limit,
        offset=offset,
    )


@router.get("/tasks/{task_id}", response_model=TaskView)
def task(task_id: UUID, a: Actor):
    return run(a, "get_task", task_id=task_id)


@router.post("/tasks", response_model=TaskView)
def create_task(body: TaskInput, a: Actor):
    return run(a, "create_task", **body.model_dump())


@router.put("/tasks/{task_id}", response_model=TaskView)
def update_task(task_id: UUID, body: TaskEdit, a: Actor):
    return run(a, "update_task", task_id=task_id, **body.model_dump())


@router.get("/leave-requests", response_model=Page[LeaveView])
def leave_requests(
    a: Actor,
    status: Literal["PENDING", "APPROVED", "REJECTED"] | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return run(a, "list_leave_requests", status=status, limit=limit, offset=offset)


@router.get("/leave-requests/{leave_id}", response_model=LeaveView)
def leave_request(leave_id: UUID, a: Actor):
    return run(a, "get_leave_request", leave_id=leave_id)


@router.post("/leave-requests", response_model=LeaveView)
def request_leave(body: LeaveInput, a: Actor):
    return run(a, "request_leave", **body.model_dump())


@router.post("/leave-requests/{leave_id}/approve", response_model=LeaveView)
def approve_leave(leave_id: UUID, a: Actor):
    return run(a, "approve_leave", leave_id=leave_id)


@router.post("/leave-requests/{leave_id}/reject", response_model=LeaveView)
def reject_leave(leave_id: UUID, body: Rejection, a: Actor):
    return run(a, "reject_leave", leave_id=leave_id, reason=body.reason)


@router.get("/tickets", response_model=Page[TicketView])
def tickets(
    a: Actor,
    query: str = "",
    status: TicketStatus | None = None,
    priority: Priority | None = None,
    assignee_id: UUID | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return run(
        a,
        "list_tickets",
        query=query,
        status=status,
        priority=priority,
        assignee_id=assignee_id,
        limit=limit,
        offset=offset,
    )


@router.get("/tickets/{ticket_id}", response_model=TicketView)
def ticket(ticket_id: UUID, a: Actor):
    return run(a, "get_ticket", ticket_id=ticket_id)


@router.post("/tickets", response_model=TicketView)
def create_ticket(body: TicketInput, a: Actor):
    return run(a, "create_ticket", **body.model_dump())


@router.get("/approvals")
def approvals(
    a: Actor,
    kind: Literal["timesheet", "leave"] | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return run(a, "list_pending_approvals", kind=kind, limit=limit, offset=offset)


@router.get("/audit-events", response_model=Page[AuditView])
def activity(
    a: Actor,
    actor_id: UUID | None = None,
    source: Literal["UI", "MCP"] | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    outcome: Literal["SUCCESS", "DENIED", "FAILED"] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return run(
        a,
        "get_recent_activity",
        actor_id=actor_id,
        source=source,
        action=action,
        resource_type=resource_type,
        outcome=outcome,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )


@router.patch("/tasks/{task_id}/assignee", response_model=TaskView)
def assign_task(task_id: UUID, body: Assignment, a: Actor):
    return run(a, "assign_task", task_id=task_id, **body.model_dump())


@router.patch("/tasks/{task_id}/status", response_model=TaskView)
def task_status(task_id: UUID, body: TaskState, a: Actor):
    return run(a, "update_task_status", task_id=task_id, **body.model_dump())


@router.patch("/tickets/{ticket_id}/assignee", response_model=TicketView)
def assign_ticket(ticket_id: UUID, body: Assignment, a: Actor):
    return run(a, "assign_ticket", ticket_id=ticket_id, **body.model_dump())


@router.patch("/tickets/{ticket_id}/status", response_model=TicketView)
def ticket_status(ticket_id: UUID, body: TicketState, a: Actor):
    return run(a, "update_ticket_status", ticket_id=ticket_id, **body.model_dump())


@router.patch("/tickets/{ticket_id}/priority", response_model=TicketView)
def ticket_priority(ticket_id: UUID, body: TicketPriority, a: Actor):
    return run(a, "update_ticket_priority", ticket_id=ticket_id, **body.model_dump())
