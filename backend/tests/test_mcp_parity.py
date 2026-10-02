"""Every exposed business operation matches its REST counterpart."""

import asyncio
from datetime import date
from uuid import UUID, uuid4
import pytest
from fastmcp import Client
from sqlalchemy import select
from backend.app.database.connection import Base
from backend.app.database import seed
from backend.app.database.seed import uid
from backend.app.models.entities import AuditEvent
from backend.app.services import portal
from backend.app.auth.context import ActorContext
from backend.tests.test_mcp import credential, tool, start_server
from backend.app.config import settings

NAMES = [
    "get_my_context",
    "search_employees",
    "get_employee",
    "list_projects",
    "get_project",
    "list_timesheets",
    "get_my_timesheet",
    "get_timesheet",
    "add_time_entry",
    "update_time_entry",
    "delete_time_entry",
    "submit_timesheet",
    "approve_timesheet",
    "reject_timesheet",
    "list_tasks",
    "get_task",
    "create_task",
    "update_task",
    "assign_task",
    "update_task_status",
    "list_leave_requests",
    "get_leave_request",
    "request_leave",
    "approve_leave",
    "reject_leave",
    "list_tickets",
    "get_ticket",
    "create_ticket",
    "assign_ticket",
    "update_ticket_priority",
    "update_ticket_status",
    "list_pending_approvals",
    "get_recent_activity",
]


def normalize(value):
    if isinstance(value, dict):
        return {
            k: normalize(v)
            for k, v in value.items()
            if k not in {"created_at", "submitted_at", "reviewed_at", "request_id", "replayed"}
        }
    if isinstance(value, list):
        return [normalize(v) for v in value]
    if isinstance(value, str):
        try:
            parsed = UUID(value)
            return value if str(parsed).startswith("00000000-") else "<generated-id>"
        except ValueError:
            return value
    return value


def prepare(name):
    def invoke(n, operation, **args):
        return portal.run(ActorContext(uid(n), "UI", str(uuid4())), operation, **args)

    entry = invoke(2, "add_time_entry", project_id=uid(101), work_date=date(2027, 3, 1), hours=2)
    sheet = entry["timesheet_id"]
    task = invoke(
        1, "create_task", title="Parity task", description="Keep details", assignee_id=uid(2)
    )
    leave = invoke(2, "request_leave", start_date=date(2027, 3, 10), end_date=date(2027, 3, 12))
    ticket = invoke(2, "create_ticket", title="Parity ticket")
    if name in ("approve_timesheet", "reject_timesheet", "list_pending_approvals"):
        invoke(2, "submit_timesheet", week=date(2027, 3, 1))
    cases = {
        "get_my_context": (2, "GET", "/context", {}),
        "search_employees": (2, "GET", "/employees", {"query": "Dinesh"}),
        "get_employee": (2, "GET", f"/employees/{uid(2)}", {"employee_id": str(uid(2))}),
        "list_projects": (2, "GET", "/projects", {}),
        "get_project": (2, "GET", f"/projects/{uid(101)}", {"project_id": str(uid(101))}),
        "list_timesheets": (1, "GET", "/timesheets", {}),
        "get_my_timesheet": (2, "GET", "/timesheets/me", {"week": "2027-03-01"}),
        "get_timesheet": (2, "GET", f"/timesheets/{sheet}", {"timesheet_id": sheet}),
        "add_time_entry": (
            2,
            "POST",
            "/time-entries",
            {"project_id": str(uid(101)), "work_date": "2027-03-02", "hours": 7},
        ),
        "update_time_entry": (
            2,
            "PUT",
            f"/time-entries/{entry['id']}",
            {
                "entry_id": entry["id"],
                "project_id": str(uid(101)),
                "work_date": "2027-03-01",
                "hours": 7,
            },
        ),
        "delete_time_entry": (
            2,
            "DELETE",
            f"/time-entries/{entry['id']}",
            {"entry_id": entry["id"]},
        ),
        "submit_timesheet": (
            2,
            "POST",
            "/timesheets/submit?week=2027-03-01",
            {"week": "2027-03-01"},
        ),
        "approve_timesheet": (1, "POST", f"/timesheets/{sheet}/approve", {"timesheet_id": sheet}),
        "reject_timesheet": (
            1,
            "POST",
            f"/timesheets/{sheet}/reject",
            {"timesheet_id": sheet, "reason": "Correct this"},
        ),
        "list_tasks": (2, "GET", "/tasks", {}),
        "get_task": (2, "GET", f"/tasks/{task['id']}", {"task_id": task["id"]}),
        "create_task": (1, "POST", "/tasks", {"title": "New task", "assignee_id": str(uid(2))}),
        "update_task": (
            1,
            "PATCH",
            f"/tasks/{task['id']}",
            {"task_id": task["id"], "changes": {"title": "New title"}},
        ),
        "assign_task": (
            1,
            "PATCH",
            f"/tasks/{task['id']}/assignee",
            {"task_id": task["id"], "assignee_id": str(uid(3))},
        ),
        "update_task_status": (
            2,
            "PATCH",
            f"/tasks/{task['id']}/status",
            {"task_id": task["id"], "status": "DONE"},
        ),
        "list_leave_requests": (2, "GET", "/leave-requests", {}),
        "get_leave_request": (
            2,
            "GET",
            f"/leave-requests/{leave['id']}",
            {"leave_id": leave["id"]},
        ),
        "request_leave": (
            2,
            "POST",
            "/leave-requests",
            {"start_date": "2027-03-20", "end_date": "2027-03-21"},
        ),
        "approve_leave": (
            1,
            "POST",
            f"/leave-requests/{leave['id']}/approve",
            {"leave_id": leave["id"]},
        ),
        "reject_leave": (
            1,
            "POST",
            f"/leave-requests/{leave['id']}/reject",
            {"leave_id": leave["id"], "reason": "Coverage"},
        ),
        "list_tickets": (2, "GET", "/tickets", {}),
        "get_ticket": (2, "GET", f"/tickets/{ticket['id']}", {"ticket_id": ticket["id"]}),
        "create_ticket": (2, "POST", "/tickets", {"title": "New ticket"}),
        "assign_ticket": (
            1,
            "PATCH",
            f"/tickets/{ticket['id']}/assignee",
            {"ticket_id": ticket["id"], "assignee_id": str(uid(3))},
        ),
        "update_ticket_priority": (
            1,
            "PATCH",
            f"/tickets/{ticket['id']}/priority",
            {"ticket_id": ticket["id"], "priority": "HIGH"},
        ),
        "update_ticket_status": (
            2,
            "PATCH",
            f"/tickets/{ticket['id']}/status",
            {"ticket_id": ticket["id"], "status": "CLOSED"},
        ),
        "list_pending_approvals": (1, "GET", "/approvals", {}),
        "get_recent_activity": (2, "GET", "/audit-events", {}),
    }
    return cases[name]


@pytest.mark.parametrize("name", NAMES)
def test_rest_mcp_operation_parity(name, database, login, client, monkeypatch):
    monkeypatch.setattr(settings, "mcp_auth_mode", "demo")
    monkeypatch.setattr(settings, "mcp_rate_limit", 10000)
    server, thread, endpoint = start_server(monkeypatch)

    def reset():
        with database.begin() as db:
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
        seed.seed()

    try:
        reset()
        actor, method, path, args = prepare(name)
        login(actor)
        retry = str(uuid4())
        creation = name in ("add_time_entry", "create_task", "request_leave", "create_ticket")
        # Path IDs are MCP arguments but not REST body/query fields.
        values = {
            k: v
            for k, v in args.items()
            if not (
                k
                in {
                    "employee_id",
                    "project_id",
                    "timesheet_id",
                    "entry_id",
                    "task_id",
                    "leave_id",
                    "ticket_id",
                }
                and str(v) in path
            )
        }
        if name == "update_task":
            values = values["changes"]
        if name == "submit_timesheet":
            values = {}
        kwargs = {"params" if method == "GET" else "json": values}
        if creation:
            kwargs["headers"] = {"Idempotency-Key": retry}
        response = client.request(method, "/api/v1" + path, **kwargs)
        assert response.status_code == 200, response.text
        expected = response.json()
        operation = "patch_task" if name == "update_task" else name
        if portal.OPERATIONS[operation]:
            with database() as db:
                audit = db.scalar(
                    select(AuditEvent)
                    .where(AuditEvent.action == operation)
                    .order_by(AuditEvent.created_at.desc())
                )
                assert audit.source == "UI" and audit.outcome == "SUCCESS"
        reset()
        actor, _, _, args = prepare(name)
        if creation:
            args["idempotency_key"] = retry

        async def scenario():
            async with Client(
                endpoint,
                timeout=10,
                auth=credential(
                    actor,
                    ["portal:read", "portal:write", "portal:review"]
                    if actor == 1
                    else ["portal:read", "portal:write"],
                ),
            ) as c:
                return await tool(c, name, **args)

        actual = asyncio.run(scenario())
        record = actual.get("record", {k: v for k, v in actual.items() if k != "request_id"})
        assert normalize(record) == normalize(expected)
        if portal.OPERATIONS[operation]:
            with database() as db:
                audit = db.scalar(
                    select(AuditEvent)
                    .where(AuditEvent.action == operation)
                    .order_by(AuditEvent.created_at.desc())
                )
                assert audit.source == "MCP" and audit.outcome == "SUCCESS"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive()
