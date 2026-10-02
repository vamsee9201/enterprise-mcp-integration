"""Protocol-level regression suite using the actual authenticated HTTP transport."""

import asyncio
import socket
import threading
import time
from datetime import date, timedelta
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from fastmcp import Client
from sqlalchemy import select, func
from backend.app.config import settings
from backend.app.auth import tokens
from backend.app.auth.context import ServiceError, ActorContext
from backend.app.database.seed import uid
from backend.app.models.entities import (
    AuditEvent,
    IdempotencyRecord,
    SessionToken,
    Ticket,
    User,
    utcnow,
)
from backend.app.services import portal
from mcp_server.server import create_app, create_server


@pytest.fixture
def mcp_http(database, monkeypatch):
    monkeypatch.setattr(settings, "mcp_auth_mode", "demo")
    monkeypatch.setattr(settings, "mcp_rate_limit", 10000)
    return start_server(monkeypatch)


def start_server(monkeypatch):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    monkeypatch.setattr(settings, "mcp_allowed_hosts", [f"127.0.0.1:{port}"])
    server = uvicorn.Server(uvicorn.Config(create_app(), log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    for _ in range(200):
        if server.started:
            break
        if not thread.is_alive():
            raise RuntimeError("MCP HTTP server failed to start")
        time.sleep(0.01)
    else:
        raise RuntimeError("MCP HTTP startup timed out")
    return server, thread, f"http://127.0.0.1:{port}/mcp"


@pytest.fixture
def endpoint(mcp_http):
    server, thread, url = mcp_http
    try:
        yield url
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive()


def credential(n=2, scopes=None):
    return tokens.issue_mcp_token(uid(n), scopes)[0]


async def tool(client, name, **args):
    result = await client.call_tool(name, args, raise_on_error=False)
    assert not result.is_error, result.content
    return result.structured_content


def test_inventory_and_contracts(endpoint):
    async def scenario():
        async with Client(endpoint, timeout=5, auth=credential()) as c:
            tools = await c.list_tools()
            assert len(tools) == 33
            for t in tools:
                assert t.outputSchema and t.description
                assert t.inputSchema["additionalProperties"] is False
                assert t.annotations.openWorldHint is False
                assert t.annotations.readOnlyHint == t.name.startswith(("get_", "list_", "search_"))
                assert (
                    not {"actor_id", "source", "user_id", "role"} & set(t.inputSchema["properties"])
                    or t.name == "get_recent_activity"
                )
            context = (await tool(c, "get_my_context"))["record"]
            assert context["user"]["id"] == str(uid(2))
            assert context["manager"]["id"] == str(uid(1))
            assert date.fromisoformat(context["week_start"]).weekday() == 0
            for bad in ({"user_id": str(uid(6))},):
                result = await c.call_tool("get_my_context", bad, raise_on_error=False)
                assert result.is_error
            result = await c.call_tool(
                "add_time_entry",
                {"project_id": str(uid(101)), "work_date": "2027-03-01", "hours": 7},
                raise_on_error=False,
            )
            assert result.is_error

    asyncio.run(scenario())


def test_http_authentication_and_guards(endpoint, database, monkeypatch):
    url = endpoint
    base = url.removesuffix("/mcp")
    assert httpx.get(base + "/health").status_code == 200
    assert httpx.get(base + "/ready").status_code == 200
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-11-25",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        },
    }
    assert httpx.post(url, headers=headers, json=body).status_code == 401
    web, _ = tokens.issue_token(uid(2))
    assert (
        httpx.post(
            url, headers={**headers, "Authorization": "Bearer " + web}, json=body
        ).status_code
        == 401
    )
    token, cid = tokens.issue_mcp_token(uid(2))
    authenticated = {**headers, "Authorization": "Bearer " + token}
    assert (
        httpx.post(
            url, headers={**authenticated, "Origin": "https://evil.example"}, json=body
        ).status_code
        == 403
    )
    assert (
        httpx.post(url, headers={**authenticated, "Host": "evil.example"}, json=body).status_code
        == 403
    )
    monkeypatch.setattr(settings, "mcp_rate_limit", 1)
    assert httpx.post(url, headers=authenticated, json=body).status_code == 200
    assert httpx.post(url, headers=authenticated, json=body).status_code == 429
    with database.begin() as db:
        db.get(User, uid(2)).active = False
    assert httpx.post(url, headers=authenticated, json=body).status_code == 401
    with database.begin() as db:
        db.get(User, uid(2)).active = True
    tokens.revoke_mcp_credential(cid)
    assert httpx.post(url, headers=authenticated, json=body).status_code == 401
    token, cid = tokens.issue_mcp_token(uid(2))
    with database.begin() as db:
        db.get(SessionToken, cid).expires_at = utcnow() - timedelta(seconds=1)
    assert (
        httpx.post(
            url, headers={**headers, "Authorization": "Bearer " + token}, json=body
        ).status_code
        == 401
    )


def test_all_module_workflows(endpoint, database):
    async def scenario():
        async with (
            Client(endpoint, timeout=5, auth=credential(2)) as employee,
            Client(
                endpoint, auth=credential(1, ["portal:read", "portal:write", "portal:review"])
            ) as manager,
            Client(
                endpoint, auth=credential(6, ["portal:read", "portal:write", "portal:review"])
            ) as admin,
        ):
            people = await tool(employee, "search_employees", query="Gilfoyle")
            await tool(employee, "get_employee", employee_id=people["items"][0]["id"])
            projects = await tool(employee, "list_projects", query="Compression")
            pid = projects["items"][0]["id"]
            await tool(employee, "get_project", project_id=pid)
            key = str(uuid4())
            entry_args = dict(project_id=pid, work_date="2027-03-01", hours=7, idempotency_key=key)
            entry = await tool(employee, "add_time_entry", **entry_args)
            assert entry["record"]["description"] == ""
            repeat = await tool(employee, "add_time_entry", **entry_args)
            assert repeat["replayed"] and repeat["record"] == entry["record"]
            conflict = await employee.call_tool(
                "add_time_entry", {**entry_args, "hours": 8}, raise_on_error=False
            )
            assert conflict.is_error
            await tool(
                employee,
                "update_time_entry",
                entry_id=entry["record"]["id"],
                project_id=pid,
                work_date="2027-03-01",
                hours=8,
            )
            extra = await tool(
                employee,
                "add_time_entry",
                project_id=pid,
                work_date="2027-03-02",
                hours=1,
                idempotency_key=str(uuid4()),
            )
            await tool(employee, "delete_time_entry", entry_id=extra["record"]["id"])
            own = await tool(employee, "get_my_timesheet", week="2027-03-01")
            sheet_id = own["record"]["id"]
            await tool(employee, "get_timesheet", timesheet_id=sheet_id)
            await tool(employee, "submit_timesheet", week="2027-03-01")
            await tool(manager, "list_pending_approvals", kind="timesheet")
            await tool(manager, "reject_timesheet", timesheet_id=sheet_id, reason="Correct hours")
            await tool(
                employee,
                "update_time_entry",
                entry_id=entry["record"]["id"],
                project_id=pid,
                work_date="2027-03-01",
                hours=7,
            )
            await tool(employee, "submit_timesheet", week="2027-03-01")
            await tool(manager, "approve_timesheet", timesheet_id=sheet_id)
            history = await tool(
                manager,
                "list_timesheets",
                employee_id=str(uid(2)),
                start_week="2027-03-01",
                end_week="2027-03-01",
                status="APPROVED",
            )
            assert history["total"] == 1
            task = (
                await tool(
                    manager,
                    "create_task",
                    title="MCP integration",
                    description="Preserve this",
                    assignee_id=str(uid(2)),
                    idempotency_key=str(uuid4()),
                )
            )["record"]
            await tool(manager, "get_task", task_id=task["id"])
            patched = (
                await tool(manager, "update_task", task_id=task["id"], changes={"title": "Updated"})
            )["record"]
            assert patched["description"] == "Preserve this"
            await tool(manager, "assign_task", task_id=task["id"], assignee_id=str(uid(3)))
            await tool(manager, "assign_task", task_id=task["id"], assignee_id=str(uid(2)))
            await tool(employee, "list_tasks", status="TODO")
            await tool(employee, "update_task_status", task_id=task["id"], status="DONE")
            leave = (
                await tool(
                    employee,
                    "request_leave",
                    start_date="2027-03-10",
                    end_date="2027-03-12",
                    idempotency_key=str(uuid4()),
                )
            )["record"]
            await tool(employee, "get_leave_request", leave_id=leave["id"])
            await tool(manager, "list_leave_requests", status="PENDING")
            await tool(manager, "reject_leave", leave_id=leave["id"], reason="Coverage required")
            leave = (
                await tool(
                    employee,
                    "request_leave",
                    start_date="2027-03-20",
                    end_date="2027-03-21",
                    idempotency_key=str(uuid4()),
                )
            )["record"]
            await tool(manager, "approve_leave", leave_id=leave["id"])
            ticket = (
                await tool(
                    employee, "create_ticket", title="MCP VPN issue", idempotency_key=str(uuid4())
                )
            )["record"]
            await tool(employee, "get_ticket", ticket_id=ticket["id"])
            await tool(manager, "assign_ticket", ticket_id=ticket["id"], assignee_id=str(uid(2)))
            await tool(manager, "update_ticket_priority", ticket_id=ticket["id"], priority="HIGH")
            await tool(employee, "update_ticket_status", ticket_id=ticket["id"], status="CLOSED")
            await tool(employee, "update_ticket_status", ticket_id=ticket["id"], status="OPEN")
            assert (await tool(employee, "list_tickets", query="MCP VPN"))["total"] == 1
            events = await tool(admin, "get_recent_activity", source="MCP")
            assert events["total"] >= 20
            assert all(e["source"] == "MCP" for e in events["items"])

    asyncio.run(scenario())
    with database() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "add_time_entry", AuditEvent.outcome == "SUCCESS")
            )
            == 2
        )


def test_scopes_roles_and_identity_isolation(endpoint, database):
    async def scenario():
        async with (
            Client(endpoint, timeout=5, auth=credential(2, ["portal:read"])) as read_only,
            Client(endpoint, timeout=5, auth=credential(3)) as other,
            Client(endpoint, timeout=5, auth=credential(2)) as employee,
        ):
            contexts = await asyncio.gather(
                tool(employee, "get_my_context"), tool(other, "get_my_context")
            )
            assert [r["record"]["user"]["id"] for r in contexts] == [str(uid(2)), str(uid(3))]
            args = {"title": "Scope test", "idempotency_key": str(uuid4())}
            assert (await read_only.call_tool("create_ticket", args, raise_on_error=False)).is_error
            ticket = (await tool(employee, "create_ticket", **args))["record"]
            assert (
                await other.call_tool(
                    "get_ticket", {"ticket_id": ticket["id"]}, raise_on_error=False
                )
            ).is_error
            assert (
                await employee.call_tool(
                    "assign_ticket",
                    {"ticket_id": ticket["id"], "assignee_id": str(uid(3))},
                    raise_on_error=False,
                )
            ).is_error

    asyncio.run(scenario())


def test_partial_task_rest_and_context(login, client):
    login(1)
    task = client.post(
        "/api/v1/tasks",
        json={
            "title": "Original",
            "description": "Keep",
            "assignee_id": str(uid(2)),
            "due_date": "2027-03-01",
        },
    ).json()
    assert (
        client.patch(f"/api/v1/tasks/{task['id']}", json={"title": "New"}).json()["description"]
        == "Keep"
    )
    assert (
        client.patch(f"/api/v1/tasks/{task['id']}", json={"due_date": None}).json()["due_date"]
        is None
    )
    assert client.patch(f"/api/v1/tasks/{task['id']}", json={"title": None}).status_code == 422
    assert client.patch(f"/api/v1/tasks/{task['id']}", json={}).status_code == 422
    assert client.get("/api/v1/context").json()["user"]["id"] == str(uid(1))
    assert client.get("/api/v1/timesheets").status_code == 200


def test_rest_idempotency_and_rollback(login, client, database):
    login(2)
    key = str(uuid4())
    headers = {"Idempotency-Key": key}
    first = client.post("/api/v1/tickets", json={"title": "One ticket"}, headers=headers)
    repeat = client.post(
        "/api/v1/tickets",
        json={"title": "One ticket", "description": "", "priority": "MEDIUM"},
        headers=headers,
    )
    assert first.json()["id"] == repeat.json()["id"] and repeat.json()["replayed"]
    assert (
        client.post("/api/v1/tickets", json={"title": "Different"}, headers=headers).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/time-entries",
            json={"project_id": str(uid(999)), "work_date": "2027-03-01", "hours": 7},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 404
    )
    with database() as db:
        assert db.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1
        assert (
            db.scalar(select(func.count()).select_from(Ticket).where(Ticket.title == "One ticket"))
            == 1
        )


def test_fail_closed_and_credential_grants(database, monkeypatch):
    monkeypatch.setattr(settings, "mcp_auth_mode", None)
    with pytest.raises(RuntimeError):
        create_server()
    with pytest.raises(ServiceError):
        tokens.issue_mcp_token(uid(2), ["portal:review"])
    with pytest.raises(ServiceError):
        tokens.issue_mcp_token(uid(999))
    with pytest.raises(ServiceError):
        tokens.issue_mcp_token(uid(2), [])


@pytest.fixture
def pg_endpoint(postgres_database, monkeypatch):
    monkeypatch.setattr(settings, "mcp_auth_mode", "demo")
    monkeypatch.setattr(settings, "mcp_rate_limit", 10000)
    server, thread, url = start_server(monkeypatch)
    try:
        yield url
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        assert not thread.is_alive()


@pytest.mark.postgres
def test_mcp_postgres_retries_and_workflow_races(pg_endpoint, postgres_database):
    async def scenario():
        async with (
            Client(pg_endpoint, timeout=10, auth=credential(2)) as a,
            Client(pg_endpoint, timeout=10, auth=credential(2)) as b,
            Client(
                pg_endpoint,
                timeout=10,
                auth=credential(1, ["portal:read", "portal:write", "portal:review"]),
            ) as manager,
            Client(
                pg_endpoint,
                timeout=10,
                auth=credential(6, ["portal:read", "portal:write", "portal:review"]),
            ) as admin,
        ):
            key = str(uuid4())
            args = dict(
                project_id=str(uid(101)), work_date="2027-04-05", hours=7, idempotency_key=key
            )
            first, replay = await asyncio.gather(
                tool(a, "add_time_entry", **args), tool(b, "add_time_entry", **args)
            )
            assert first["record"]["id"] == replay["record"]["id"]
            assert sum(r["replayed"] for r in (first, replay)) == 1

            async def call(client, name, args):
                return await client.call_tool(name, args, raise_on_error=False)

            hours = await asyncio.gather(
                call(a, "add_time_entry", {**args, "hours": 10, "idempotency_key": str(uuid4())}),
                call(b, "add_time_entry", {**args, "hours": 10, "idempotency_key": str(uuid4())}),
            )
            assert sum(r.is_error for r in hours) == 1
            sheet = (await tool(a, "submit_timesheet", week="2027-04-05"))["record"]
            decisions = await asyncio.gather(
                call(manager, "approve_timesheet", {"timesheet_id": sheet["id"]}),
                call(
                    admin,
                    "reject_timesheet",
                    {"timesheet_id": sheet["id"], "reason": "Concurrent review"},
                ),
            )
            assert sum(r.is_error for r in decisions) == 1
            leave_args = dict(start_date="2027-04-15", end_date="2027-04-17")
            leaves = await asyncio.gather(
                call(a, "request_leave", {**leave_args, "idempotency_key": str(uuid4())}),
                call(b, "request_leave", {**leave_args, "idempotency_key": str(uuid4())}),
            )
            assert sum(r.is_error for r in leaves) == 1
            leave = next(r.structured_content["record"] for r in leaves if not r.is_error)
            decisions = await asyncio.gather(
                call(manager, "approve_leave", {"leave_id": leave["id"]}),
                call(
                    admin, "reject_leave", {"leave_id": leave["id"], "reason": "Concurrent review"}
                ),
            )
            assert sum(r.is_error for r in decisions) == 1

    asyncio.run(scenario())
    with postgres_database() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(IdempotencyRecord)
                .where(IdempotencyRecord.operation == "add_time_entry")
            )
            == 2
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.action.in_(["approve_timesheet", "reject_timesheet"]),
                    AuditEvent.outcome == "SUCCESS",
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(
                    AuditEvent.action.in_(["approve_leave", "reject_leave"]),
                    AuditEvent.outcome == "SUCCESS",
                )
            )
            == 1
        )


def test_replay_rechecks_access_and_key_actor_scope(call, database):
    key = uuid4()
    args = dict(title="Retry access", assignee_id=uid(2))
    actor = ActorContext(uid(1), "MCP", str(uuid4()))
    task = portal.run(actor, "create_task", idempotency_key=key, **args)
    call(6, "assign_task", task_id=UUID(task["id"]), assignee_id=uid(5))
    with pytest.raises(ServiceError) as error:
        portal.run(actor, "create_task", idempotency_key=key, **args)
    assert error.value.code == 403
    another = portal.run(
        ActorContext(uid(6), "MCP", str(uuid4())), "create_task", idempotency_key=key, **args
    )
    assert another["id"] != task["id"]


@pytest.mark.parametrize(
    "method,path", [("post", "/api/v1/__test/reset"), ("post", "/api/v1/__test/mcp-demo")]
)
def test_test_only_routes_are_absent(client, method, path):
    assert getattr(client, method)(path).status_code == 404


@pytest.mark.parametrize(
    "operation,actor,args",
    [
        (
            "add_time_entry",
            2,
            {"project_id": uid(101), "work_date": date(2027, 6, 7), "hours": "7.00"},
        ),
        ("create_task", 1, {"title": "Retry task", "assignee_id": uid(2)}),
        ("request_leave", 2, {"start_date": date(2027, 6, 15), "end_date": date(2027, 6, 17)}),
        ("create_ticket", 2, {"title": "Retry ticket"}),
    ],
)
def test_creation_retry_contracts(operation, actor, args, database):
    context = ActorContext(uid(actor), "MCP", str(uuid4()))
    key = uuid4()
    first = portal.run(context, operation, idempotency_key=key, **args)
    normalized = {**args}
    if operation == "add_time_entry":
        normalized["hours"] = 7
    if operation in ("create_task", "create_ticket", "add_time_entry"):
        normalized["description"] = ""
    repeat = portal.run(context, operation, idempotency_key=key, **normalized)
    assert repeat["id"] == first["id"] and repeat["replayed"]
    with database() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == operation, AuditEvent.outcome == "SUCCESS")
            )
            == 1
        )
        assert db.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1


def test_timesheet_history_visibility(call):
    call(2, "add_time_entry", project_id=uid(101), work_date=date(2027, 6, 7), hours=1)
    call(3, "add_time_entry", project_id=uid(101), work_date=date(2027, 6, 14), hours=1)
    assert call(2, "list_timesheets")["total"] == 1
    assert call(1, "list_timesheets")["total"] == 2
    assert call(4, "list_timesheets")["total"] == 0
    assert call(6, "list_timesheets", start_week=date(2027, 6, 14))["total"] == 1
    with pytest.raises(ServiceError):
        call(2, "list_timesheets", employee_id=uid(3))
    with pytest.raises(ServiceError):
        call(2, "list_timesheets", start_week=date(2027, 6, 14), end_week=date(2027, 6, 7))
