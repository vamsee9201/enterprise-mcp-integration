from datetime import date
from decimal import Decimal
from uuid import UUID
import pytest
from sqlalchemy import select, func
from backend.app.auth.context import ServiceError
from backend.app.database.seed import uid
from backend.app.models.entities import (
    AuditEvent,
    Timesheet,
    TimeEntry,
    Project,
    Membership,
)

DAY = date(2026, 9, 30)


def add(call, user=2, hours=7, **changes):
    return call(
        user,
        "add_time_entry",
        **{
            "project_id": uid(101),
            "work_date": DAY,
            "hours": hours,
            "description": "MCP integration work",
            **changes,
        },
    )


def sheet_id(call, user=2):
    return UUID(call(user, "get_my_timesheet", week=DAY)["id"])


def test_full_timesheet_flow(call, database):
    add(call)
    sheet = call(2, "get_my_timesheet", week=DAY)
    assert sheet["week_start"] == "2026-09-28" and sheet["total_hours"] == 7
    call(2, "submit_timesheet", week=DAY)
    assert call(1, "list_pending_approvals")["total"] == 1
    approved = call(1, "approve_timesheet", timesheet_id=UUID(sheet["id"]))
    assert approved["status"] == "APPROVED" and approved["reviewer_name"] == "Maya Chen"
    with database() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.outcome == "SUCCESS")
            )
            == 3
        )


def test_rejection_edit_resubmit(call):
    entry = add(call)
    call(2, "submit_timesheet", week=DAY)
    sid = sheet_id(call)
    call(1, "reject_timesheet", timesheet_id=sid, reason="Please clarify work")
    call(
        2,
        "update_time_entry",
        entry_id=UUID(entry["id"]),
        project_id=uid(101),
        work_date=DAY,
        hours=8,
        description="Implemented backend services",
    )
    draft = call(2, "get_my_timesheet", week=DAY)
    assert draft["status"] == "DRAFT" and draft["rejection_reason"] is None
    assert draft["reviewer_id"] is None and draft["submitted_at"] is None
    assert call(2, "submit_timesheet", week=DAY)["status"] == "SUBMITTED"


@pytest.mark.parametrize("hours", [0, -1, 25, Decimal("1.234")])
def test_invalid_hours(call, database, hours):
    with pytest.raises(ServiceError):
        add(call, hours=hours)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(TimeEntry)) == 0
        assert db.scalar(select(func.count()).select_from(Timesheet)) == 0


def test_daily_total_and_update_exclusion(call):
    first = add(call, hours=20)
    with pytest.raises(ServiceError, match="Daily hours"):
        add(call, hours=5)
    call(
        2,
        "update_time_entry",
        entry_id=UUID(first["id"]),
        project_id=uid(101),
        work_date=DAY,
        hours=24,
        description="Work",
    )
    assert call(2, "get_my_timesheet", week=DAY)["total_hours"] == 24


def test_date_cannot_move_to_another_week(call):
    entry = add(call)
    with pytest.raises(ServiceError, match="within the timesheet week"):
        call(
            2,
            "update_time_entry",
            entry_id=UUID(entry["id"]),
            project_id=uid(101),
            work_date=date(2026, 10, 5),
            hours=7,
            description="Work",
        )


def test_project_requires_active_membership(call, database):
    with database.begin() as db:
        db.delete(db.get(Membership, (uid(101), uid(2))))
    with pytest.raises(ServiceError, match="assigned project"):
        add(call)
    with database.begin() as db:
        db.add(Membership(project_id=uid(101), user_id=uid(2)))
        db.get(Project, uid(101)).active = False
    with pytest.raises(ServiceError):
        add(call)


def test_submission_requires_entries(call):
    with pytest.raises(ServiceError, match="at least one entry"):
        call(2, "submit_timesheet", week=DAY)
    entry = add(call)
    call(2, "delete_time_entry", entry_id=UUID(entry["id"]))
    with pytest.raises(ServiceError):
        call(2, "submit_timesheet", week=DAY)


@pytest.mark.parametrize("reviewed", [False, True])
def test_locked_timesheets(call, reviewed):
    entry = add(call)
    call(2, "submit_timesheet", week=DAY)
    if reviewed:
        call(1, "approve_timesheet", timesheet_id=sheet_id(call))
    with pytest.raises(ServiceError, match="locked"):
        add(call)
    with pytest.raises(ServiceError, match="locked"):
        call(2, "delete_time_entry", entry_id=UUID(entry["id"]))


def test_ownership_team_and_self_review(call, database):
    entry = add(call)
    sid = sheet_id(call)
    for user in (3, 4):
        with pytest.raises(ServiceError) as error:
            call(user, "get_timesheet", timesheet_id=sid)
        assert error.value.code == 403
    assert call(6, "get_timesheet", timesheet_id=sid)["id"] == str(sid)
    with pytest.raises(ServiceError):
        call(1, "delete_time_entry", entry_id=UUID(entry["id"]))
    call(2, "submit_timesheet", week=DAY)
    with pytest.raises(ServiceError, match="own request"):
        call(2, "approve_timesheet", timesheet_id=sid)
    with database() as db:
        assert (
            db.scalar(
                select(func.count()).select_from(AuditEvent).where(AuditEvent.outcome == "DENIED")
            )
            >= 2
        )


def test_rejection_reason_and_duplicate_decision(call):
    add(call)
    call(2, "submit_timesheet", week=DAY)
    sid = sheet_id(call)
    with pytest.raises(ServiceError):
        call(1, "reject_timesheet", timesheet_id=sid, reason="  ")
    call(1, "approve_timesheet", timesheet_id=sid)
    with pytest.raises(ServiceError) as e:
        call(6, "approve_timesheet", timesheet_id=sid)
    assert e.value.code == 409


def test_leave_dates_overlap_and_review(call):
    with pytest.raises(ServiceError):
        call(2, "request_leave", start_date=date(2026, 10, 14), end_date=date(2026, 10, 12))
    leave = call(
        2,
        "request_leave",
        start_date=date(2026, 10, 12),
        end_date=date(2026, 10, 14),
        reason="Family trip",
    )
    with pytest.raises(ServiceError, match="overlap"):
        call(2, "request_leave", start_date=date(2026, 10, 14), end_date=date(2026, 10, 15))
    with pytest.raises(ServiceError):
        call(4, "approve_leave", leave_id=UUID(leave["id"]))
    call(1, "reject_leave", leave_id=UUID(leave["id"]), reason="Coverage needed")
    new = call(2, "request_leave", start_date=date(2026, 10, 12), end_date=date(2026, 10, 14))
    call(1, "approve_leave", leave_id=UUID(new["id"]))
    with pytest.raises(ServiceError):
        call(2, "request_leave", start_date=date(2026, 10, 13), end_date=date(2026, 10, 13))


def test_task_permissions_and_reopening(call):
    with pytest.raises(ServiceError):
        call(2, "create_task", title="Test", assignee_id=uid(2))
    with pytest.raises(ServiceError):
        call(1, "create_task", title="Test", assignee_id=uid(5))
    task = call(1, "create_task", title="Write tests", assignee_id=uid(2), project_id=uid(101))
    tid = UUID(task["id"])
    with pytest.raises(ServiceError):
        call(3, "update_task_status", task_id=tid, status="DONE")
    assert call(2, "update_task_status", task_id=tid, status="DONE")["status"] == "DONE"
    assert call(2, "update_task_status", task_id=tid, status="TODO")["status"] == "TODO"
    with pytest.raises(ServiceError):
        call(2, "update_task", task_id=tid, title="Changed")
    with pytest.raises(ServiceError):
        call(1, "assign_task", task_id=tid, assignee_id=uid(5))
    assert call(1, "assign_task", task_id=tid, assignee_id=uid(3))["assignee_id"] == str(uid(3))


def test_ticket_ownership_assignment_and_transitions(call):
    ticket = call(2, "create_ticket", title="VPN issue", priority="HIGH")
    tid = UUID(ticket["id"])
    with pytest.raises(ServiceError):
        call(3, "get_ticket", ticket_id=tid)
    with pytest.raises(ServiceError):
        call(2, "assign_ticket", ticket_id=tid, assignee_id=uid(6))
    call(1, "assign_ticket", ticket_id=tid, assignee_id=uid(5))
    with pytest.raises(ServiceError):
        call(2, "update_ticket_priority", ticket_id=tid, priority="LOW")
    with pytest.raises(ServiceError):
        call(1, "update_ticket_status", ticket_id=tid, status="CLOSED")
    for status in ("IN_PROGRESS", "RESOLVED", "CLOSED", "OPEN"):
        assert call(2, "update_ticket_status", ticket_id=tid, status=status)["status"] == status


def test_directory_filters_and_pagination(call):
    page = call(2, "search_employees", query="Maya", limit=1)
    assert page["total"] == 3 and len(page["items"]) == 1
    page = call(2, "search_employees", department="Engineering", manager_id=uid(1))
    assert {u["name"] for u in page["items"]} == {"Vamsee Krishna", "Alex Morgan"}
    assert call(2, "get_employee", employee_id=uid(2))["manager_name"] == "Maya Chen"
    with pytest.raises(ServiceError):
        call(2, "search_employees", limit=101)


def test_audit_visibility_and_filters(call):
    add(call, user=2)
    add(call, user=5)
    assert call(2, "get_recent_activity")["total"] == 1
    assert call(1, "get_recent_activity")["total"] == 1
    assert call(6, "get_recent_activity")["total"] == 2
    assert (
        call(
            2,
            "get_recent_activity",
            source="UI",
            resource_type="time_entry",
            outcome="SUCCESS",
            action="add_time_entry",
        )["total"]
        == 1
    )
    assert call(2, "get_recent_activity", actor_id=uid(5))["total"] == 0


def test_audit_failure_rolls_back_business_change(call, database, monkeypatch):
    from sqlalchemy.orm import Session

    original = Session.add

    def fail_audit(self, obj, *args, **kwargs):
        if isinstance(obj, AuditEvent):
            raise RuntimeError("Audit unavailable")
        return original(self, obj, *args, **kwargs)

    monkeypatch.setattr(Session, "add", fail_audit)
    with pytest.raises(RuntimeError):
        add(call)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(TimeEntry)) == 0
        assert db.scalar(select(func.count()).select_from(Timesheet)) == 0
