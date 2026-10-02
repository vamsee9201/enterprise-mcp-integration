"""Explicit typed tools. Business logic lives in shared services."""

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from pydantic import Field
from mcp.types import ToolAnnotations
from backend.app.schemas.inputs import TaskPatch, TaskStatus, TicketStatus, Priority
from backend.app.schemas.outputs import (
    UserView,
    ProjectView,
    SheetView,
    EntryView,
    TaskView,
    LeaveView,
    TicketView,
    AuditView,
)
from mcp_server.contracts import ContextView, DeletedView, ReviewView, RecordResult, PageResult
from mcp_server.adapter import invoke

QueryText = Annotated[str, Field(max_length=200)]
FilterText = Annotated[str, Field(max_length=100)]
Limit = Annotated[int, Field(ge=1, le=100)]
Offset = Annotated[int, Field(ge=0)]
Hours = Annotated[Decimal, Field(gt=0, le=24, max_digits=4, decimal_places=2)]
Title = Annotated[str, Field(min_length=1, max_length=200)]
Description = Annotated[str, Field(max_length=1000)]
LongDescription = Annotated[str, Field(max_length=2000)]
Reason = Annotated[str, Field(min_length=1, max_length=1000)]
SheetStatus = Literal["DRAFT", "SUBMITTED", "APPROVED", "REJECTED"]
LeaveStatus = Literal["PENDING", "APPROVED", "REJECTED"]


def register_tools(server):
    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def get_my_context() -> RecordResult[ContextView]:
        """Get your identity, manager, Chicago date and Monday-start week."""
        return await invoke("get_my_context")

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def search_employees(
        query: QueryText = "",
        department: FilterText | None = None,
        manager_id: UUID | None = None,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> PageResult[UserView]:
        """Search active employees by name, email, department or manager; use returned IDs for assignment."""
        return await invoke(
            "search_employees",
            query=query,
            department=department,
            manager_id=manager_id,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def get_employee(employee_id: UUID) -> RecordResult[UserView]:
        """Get an employee including their manager ID and name."""
        return await invoke("get_employee", employee_id=employee_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def list_projects(
        query: QueryText = "", limit: Limit = 50, offset: Offset = 0
    ) -> PageResult[ProjectView]:
        """Find active projects assigned to you; admins see all active projects."""
        return await invoke("list_projects", query=query, limit=limit, offset=offset)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def get_project(project_id: UUID) -> RecordResult[ProjectView]:
        """Read an authorized project."""
        return await invoke("get_project", project_id=project_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def list_timesheets(
        employee_id: UUID | None = None,
        start_week: date | None = None,
        end_week: date | None = None,
        status: SheetStatus | None = None,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> PageResult[SheetView]:
        """Find historical sheets in your ownership, direct-report or admin scope; inclusive Monday-normalized weeks."""
        return await invoke(
            "list_timesheets",
            employee_id=employee_id,
            start_week=start_week,
            end_week=end_week,
            status=status,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def get_my_timesheet(week: date) -> RecordResult[SheetView]:
        """Read your selected week, normalized to Monday. Empty weeks are draft with no persisted zero entries."""
        return await invoke("get_my_timesheet", week=week)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def get_timesheet(timesheet_id: UUID) -> RecordResult[SheetView]:
        """Read a known sheet within your ownership, team or admin scope."""
        return await invoke("get_timesheet", timesheet_id=timesheet_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=True
        )
    )
    async def add_time_entry(
        project_id: UUID,
        work_date: date,
        hours: Hours,
        idempotency_key: UUID,
        description: Description = "",
    ) -> RecordResult[EntryView]:
        """Log positive decimal hours on your editable sheet and active assigned project. Description is optional; daily total cannot exceed 24. Reuse the retry key only for an identical retry."""
        return await invoke(
            "add_time_entry",
            project_id=project_id,
            work_date=work_date,
            hours=hours,
            idempotency_key=idempotency_key,
            description=description,
        )

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def update_time_entry(
        entry_id: UUID,
        project_id: UUID,
        work_date: date,
        hours: Hours,
        description: Description = "",
    ) -> RecordResult[EntryView]:
        """Replace an entry on your editable sheet. Supply its project, date and hours; omitted description becomes empty."""
        return await invoke(
            "update_time_entry",
            entry_id=entry_id,
            project_id=project_id,
            work_date=work_date,
            hours=hours,
            description=description,
        )

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def delete_time_entry(entry_id: UUID) -> RecordResult[DeletedView]:
        """Remove an entry on your editable sheet; use deletion rather than logging zero hours."""
        return await invoke("delete_time_entry", entry_id=entry_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def submit_timesheet(week: date) -> RecordResult[SheetView]:
        """Submit your nonempty draft week for review. Submitted sheets become locked."""
        return await invoke("submit_timesheet", week=week)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def approve_timesheet(timesheet_id: UUID) -> RecordResult[SheetView]:
        """Approve a submitted direct-report sheet, or any authorized sheet as admin. Self-approval is forbidden."""
        return await invoke("approve_timesheet", timesheet_id=timesheet_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def reject_timesheet(timesheet_id: UUID, reason: Reason) -> RecordResult[SheetView]:
        """Reject an authorized submitted sheet with a nonblank reason. Self-review is forbidden."""
        return await invoke("reject_timesheet", timesheet_id=timesheet_id, reason=reason)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def list_tasks(
        query: QueryText = "",
        status: TaskStatus | None = None,
        assignee_id: UUID | None = None,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> PageResult[TaskView]:
        """Find tasks within your employee, team or admin scope."""
        return await invoke(
            "list_tasks",
            query=query,
            status=status,
            assignee_id=assignee_id,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def get_task(task_id: UUID) -> RecordResult[TaskView]:
        """Read an authorized task."""
        return await invoke("get_task", task_id=task_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=True
        )
    )
    async def create_task(
        title: Title,
        assignee_id: UUID,
        idempotency_key: UUID,
        description: LongDescription = "",
        project_id: UUID | None = None,
        due_date: date | None = None,
    ) -> RecordResult[TaskView]:
        """Managers create tasks assigned to self or direct reports; admins may assign any active user."""
        return await invoke(
            "create_task",
            title=title,
            assignee_id=assignee_id,
            idempotency_key=idempotency_key,
            description=description,
            project_id=project_id,
            due_date=due_date,
        )

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def update_task(task_id: UUID, changes: TaskPatch) -> RecordResult[TaskView]:
        """Partially edit authorized task details as manager/admin. Omitted fields remain unchanged; null clears only project or due date."""
        return await invoke("patch_task", task_id=task_id, **changes.model_dump(exclude_unset=True))

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def assign_task(task_id: UUID, assignee_id: UUID) -> RecordResult[TaskView]:
        """Managers assign authorized tasks only to self or direct reports; admins may assign any active user."""
        return await invoke("assign_task", task_id=task_id, assignee_id=assignee_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def update_task_status(task_id: UUID, status: TaskStatus) -> RecordResult[TaskView]:
        """Set an authorized task to TODO, IN_PROGRESS or DONE, including reopening completed work."""
        return await invoke("update_task_status", task_id=task_id, status=status)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def list_leave_requests(
        status: LeaveStatus | None = None, limit: Limit = 50, offset: Offset = 0
    ) -> PageResult[LeaveView]:
        """List leave within your employee, team or admin scope."""
        return await invoke("list_leave_requests", status=status, limit=limit, offset=offset)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def get_leave_request(leave_id: UUID) -> RecordResult[LeaveView]:
        """Read an authorized leave request."""
        return await invoke("get_leave_request", leave_id=leave_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=True
        )
    )
    async def request_leave(
        start_date: date, end_date: date, idempotency_key: UUID, reason: Description = ""
    ) -> RecordResult[LeaveView]:
        """Request your own leave using inclusive calendar dates. Pending/approved overlaps and reversed ranges are rejected."""
        return await invoke(
            "request_leave",
            start_date=start_date,
            end_date=end_date,
            idempotency_key=idempotency_key,
            reason=reason,
        )

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def approve_leave(leave_id: UUID) -> RecordResult[LeaveView]:
        """Approve pending direct-report leave, or authorized leave as admin. Self-approval is forbidden."""
        return await invoke("approve_leave", leave_id=leave_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def reject_leave(leave_id: UUID, reason: Reason) -> RecordResult[LeaveView]:
        """Reject authorized pending leave with a nonblank reason. Self-review is forbidden."""
        return await invoke("reject_leave", leave_id=leave_id, reason=reason)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def list_tickets(
        query: QueryText = "",
        status: TicketStatus | None = None,
        priority: Priority | None = None,
        assignee_id: UUID | None = None,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> PageResult[TicketView]:
        """Employees find tickets they created or are currently assigned; managers/admins see all."""
        return await invoke(
            "list_tickets",
            query=query,
            status=status,
            priority=priority,
            assignee_id=assignee_id,
            limit=limit,
            offset=offset,
        )

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def get_ticket(ticket_id: UUID) -> RecordResult[TicketView]:
        """Read a ticket within creator, current-assignee, manager or admin access."""
        return await invoke("get_ticket", ticket_id=ticket_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=True
        )
    )
    async def create_ticket(
        title: Title,
        idempotency_key: UUID,
        description: LongDescription = "",
        priority: Priority = "MEDIUM",
    ) -> RecordResult[TicketView]:
        """Create your own support ticket with optional description and initial priority."""
        return await invoke(
            "create_ticket",
            title=title,
            idempotency_key=idempotency_key,
            description=description,
            priority=priority,
        )

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def assign_ticket(ticket_id: UUID, assignee_id: UUID) -> RecordResult[TicketView]:
        """Managers/admins assign tickets to active users. Reassignment removes former assignee access unless also creator."""
        return await invoke("assign_ticket", ticket_id=ticket_id, assignee_id=assignee_id)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def update_ticket_priority(
        ticket_id: UUID, priority: Priority
    ) -> RecordResult[TicketView]:
        """Change an existing ticket priority as manager/admin."""
        return await invoke("update_ticket_priority", ticket_id=ticket_id, priority=priority)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=False, openWorldHint=False, destructiveHint=True, idempotentHint=False
        )
    )
    async def update_ticket_status(
        ticket_id: UUID, status: TicketStatus
    ) -> RecordResult[TicketView]:
        """Creators, current assignees, managers and admins may select ANY ticket status, including direct closure and reopening."""
        return await invoke("update_ticket_status", ticket_id=ticket_id, status=status)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def list_pending_approvals(
        kind: Literal["timesheet", "leave"] | None = None, limit: Limit = 50, offset: Offset = 0
    ) -> PageResult[ReviewView]:
        """Managers/admins list pending authorized sheet and leave reviews, excluding their own requests."""
        return await invoke("list_pending_approvals", kind=kind, limit=limit, offset=offset)

    @server.tool(
        annotations=ToolAnnotations(
            readOnlyHint=True, openWorldHint=False, destructiveHint=False, idempotentHint=True
        )
    )
    async def get_recent_activity(
        actor_id: UUID | None = None,
        source: Literal["UI", "MCP"] | None = None,
        action: FilterText | None = None,
        resource_type: Literal["timesheet", "time_entry", "task", "leave", "ticket"] | None = None,
        outcome: Literal["SUCCESS", "DENIED", "FAILED"] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: Limit = 50,
        offset: Offset = 0,
    ) -> PageResult[AuditView]:
        """Filter audit events within your actor/team/admin scope. Dates are inclusive Chicago calendar days. Source is a filter, never the acting source."""
        return await invoke(
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

    for tool in (
        get_my_context,
        search_employees,
        get_employee,
        list_projects,
        get_project,
        list_timesheets,
        get_my_timesheet,
        get_timesheet,
        add_time_entry,
        update_time_entry,
        delete_time_entry,
        submit_timesheet,
        approve_timesheet,
        reject_timesheet,
        list_tasks,
        get_task,
        create_task,
        update_task,
        assign_task,
        update_task_status,
        list_leave_requests,
        get_leave_request,
        request_leave,
        approve_leave,
        reject_leave,
        list_tickets,
        get_ticket,
        create_ticket,
        assign_ticket,
        update_ticket_priority,
        update_ticket_status,
        list_pending_approvals,
        get_recent_activity,
    ):
        tool.parameters["additionalProperties"] = False
