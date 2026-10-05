"""Reproducible workflow demo. Tokens stay in environment variables, never arguments."""

import argparse
import asyncio
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


async def demonstrate(url, employee_token, manager_token, admin_token, week, cloud_run_token=None):
    async def invoke(client, name, **args):
        result = await client.call_tool(name, args)
        return result.structured_content

    def connect(token):
        headers = (
            {"X-Serverless-Authorization": f"Bearer {cloud_run_token}"} if cloud_run_token else None
        )
        return Client(StreamableHttpTransport(url, auth=token, headers=headers), timeout=60)

    async with (
        connect(employee_token) as employee,
        connect(manager_token) as manager,
        connect(admin_token) as admin,
    ):
        context = (await invoke(employee, "get_my_context"))["record"]
        manager_context = (await invoke(manager, "get_my_context"))["record"]
        admin_context = (await invoke(admin, "get_my_context"))["record"]
        if (
            context["user"]["name"] != "Dinesh Chugtai"
            or manager_context["user"]["name"] != "Bertram Gilfoyle"
            or admin_context["user"]["role"] != "ADMIN"
        ):
            raise ValueError("Demo requires Dinesh, Gilfoyle and admin credentials")
        project = (await invoke(employee, "list_projects", query="Compression Engine"))["items"][0]
        key = str(uuid4())
        args = dict(
            project_id=project["id"], work_date=week.isoformat(), hours=7, idempotency_key=key
        )
        entry = await invoke(employee, "add_time_entry", **args)
        replay = await invoke(employee, "add_time_entry", **args)
        assert replay["replayed"] and replay["record"]["id"] == entry["record"]["id"]
        sheet = (await invoke(employee, "submit_timesheet", week=week.isoformat()))["record"]
        await invoke(manager, "list_pending_approvals")
        await invoke(manager, "approve_timesheet", timesheet_id=sheet["id"])
        task = (
            await invoke(
                manager,
                "create_task",
                title="MCP demo integration",
                assignee_id=context["user"]["id"],
                idempotency_key=str(uuid4()),
            )
        )["record"]
        await invoke(employee, "list_tasks", status="TODO")
        await invoke(employee, "update_task_status", task_id=task["id"], status="DONE")
        leave = (
            await invoke(
                employee,
                "request_leave",
                start_date=(week + timedelta(days=14)).isoformat(),
                end_date=(week + timedelta(days=16)).isoformat(),
                idempotency_key=str(uuid4()),
            )
        )["record"]
        await invoke(manager, "reject_leave", leave_id=leave["id"], reason="Team coverage required")
        ticket = (
            await invoke(
                employee, "create_ticket", title="MCP demo VPN issue", idempotency_key=str(uuid4())
            )
        )["record"]
        await invoke(
            manager, "assign_ticket", ticket_id=ticket["id"], assignee_id=context["user"]["id"]
        )
        await invoke(employee, "update_ticket_status", ticket_id=ticket["id"], status="CLOSED")
        await invoke(employee, "update_ticket_status", ticket_id=ticket["id"], status="OPEN")
        directory = await invoke(employee, "search_employees", query="Dinesh")
        await invoke(employee, "get_employee", employee_id=directory["items"][0]["id"])
        await invoke(manager, "list_timesheets", employee_id=context["user"]["id"])
        activity = await invoke(admin, "get_recent_activity", source="MCP")
        # Manager requests need admin review; a manager cannot approve their own.
        own = (
            await invoke(
                manager,
                "request_leave",
                start_date=(week + timedelta(days=21)).isoformat(),
                end_date=(week + timedelta(days=21)).isoformat(),
                idempotency_key=str(uuid4()),
            )
        )["record"]
        assert (
            await manager.call_tool("approve_leave", {"leave_id": own["id"]}, raise_on_error=False)
        ).is_error
        assert (
            await employee.call_tool(
                "assign_ticket",
                {"ticket_id": ticket["id"], "assignee_id": manager_context["user"]["id"]},
                raise_on_error=False,
            )
        ).is_error
        assert (
            await employee.call_tool(
                "get_leave_request", {"leave_id": own["id"]}, raise_on_error=False
            )
        ).is_error
        await invoke(admin, "approve_leave", leave_id=own["id"])
        return {
            "week": week.isoformat(),
            "timesheet_id": sheet["id"],
            "task_id": task["id"],
            "ticket_id": ticket["id"],
            "leave_id": leave["id"],
            "mcp_activity_count": activity["total"],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:8001/mcp")
    parser.add_argument(
        "--week",
        type=date.fromisoformat,
        required=True,
        help="Use an empty Monday-start week; this demo creates records",
    )
    args = parser.parse_args()
    if args.week.weekday() != 0:
        parser.error("Choose a Monday")
    names = ["PIED_PIPER_EMPLOYEE_TOKEN", "PIED_PIPER_MANAGER_TOKEN", "PIED_PIPER_ADMIN_TOKEN"]
    if any(not os.environ.get(name) for name in names):
        parser.error("Set the three PIED_PIPER persona token environment variables")
    print(
        json.dumps(
            asyncio.run(
                demonstrate(
                    args.url,
                    *(os.environ[n] for n in names),
                    args.week,
                    os.environ.get("CLOUD_RUN_ID_TOKEN"),
                )
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
