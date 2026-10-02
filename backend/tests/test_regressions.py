"""Business boundaries that must stay intact as new features are added."""

from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import select

from backend.app.auth.context import ServiceError
from backend.app.database.seed import uid
from backend.app.models.entities import AuditEvent, Ticket, User


@pytest.mark.parametrize("actor", [2, 3, 1, 6], ids=["creator", "assignee", "manager", "admin"])
@pytest.mark.parametrize("initial", ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"])
@pytest.mark.parametrize("target", ["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"])
def test_ticket_transition_matrix(call, database, actor, initial, target):
    ticket = call(2, "create_ticket", title="Transition contract")
    tid = UUID(ticket["id"])
    call(1, "assign_ticket", ticket_id=tid, assignee_id=uid(3))
    with database.begin() as db:
        db.get(Ticket, tid).status = initial
    assert call(actor, "update_ticket_status", ticket_id=tid, status=target)["status"] == target
    events = call(actor, "get_recent_activity", action="update_ticket_status")["items"]
    assert len(events) == 1
    assert events[0]["outcome"] == "SUCCESS"


def test_invalid_ticket_status_is_rejected_and_audited(call):
    ticket = call(2, "create_ticket", title="Invalid status contract")
    tid = UUID(ticket["id"])
    with pytest.raises(ServiceError) as error:
        call(2, "update_ticket_status", ticket_id=tid, status="INVALID")
    assert error.value.code == 422
    assert call(2, "get_ticket", ticket_id=tid)["status"] == "OPEN"
    events = call(2, "get_recent_activity", action="update_ticket_status")["items"]
    assert events[0]["outcome"] == "FAILED"


def test_leave_self_review_duplicate_decision_and_required_reason(call):
    leave = call(4, "request_leave", start_date=date(2027, 2, 1), end_date=date(2027, 2, 1))
    lid = UUID(leave["id"])
    for action in ("approve_leave", "reject_leave"):
        args = {"reason": "Cannot review myself"} if action == "reject_leave" else {}
        with pytest.raises(ServiceError, match="own request"):
            call(4, action, leave_id=lid, **args)
    assert call(4, "list_pending_approvals")["total"] == 0
    with pytest.raises(ServiceError):
        call(6, "reject_leave", leave_id=lid, reason="  ")
    assert call(6, "approve_leave", leave_id=lid)["reviewer_id"] == str(uid(6))
    with pytest.raises(ServiceError) as error:
        call(6, "reject_leave", leave_id=lid, reason="Second decision")
    assert error.value.code == 409
    assert call(4, "get_leave_request", leave_id=lid)["status"] == "APPROVED"


def test_combined_review_queue_filters_team_scope_and_pagination(call):
    call(2, "add_time_entry", project_id=uid(101), work_date=date(2027, 3, 1), hours=7)
    sheet = call(2, "submit_timesheet", week=date(2027, 3, 1))
    leave = call(3, "request_leave", start_date=date(2027, 3, 2), end_date=date(2027, 3, 3))
    call(5, "request_leave", start_date=date(2027, 3, 2), end_date=date(2027, 3, 3))
    assert call(1, "list_pending_approvals", kind="timesheet")["items"][0]["id"] == sheet["id"]
    assert call(1, "list_pending_approvals", kind="leave")["items"][0]["id"] == leave["id"]
    first = call(1, "list_pending_approvals", limit=1, offset=0)
    second = call(1, "list_pending_approvals", limit=1, offset=1)
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert call(4, "list_pending_approvals")["total"] == 1
    assert call(6, "list_pending_approvals")["total"] == 3
    with pytest.raises(ServiceError) as error:
        call(2, "list_pending_approvals")
    assert error.value.code == 403


@pytest.mark.parametrize(
    "database_fixture",
    [
        "database",
        pytest.param("postgres_database", marks=pytest.mark.postgres),
    ],
)
def test_activity_dates_use_inclusive_chicago_days(call, request, database_fixture):
    database = request.getfixturevalue(database_fixture)
    # June 1 in Chicago is June 1 05:00 UTC through June 2 04:59:59 UTC.
    times = [
        datetime(2027, 6, 1, 4, 59, 59, tzinfo=timezone.utc),
        datetime(2027, 6, 1, 5, tzinfo=timezone.utc),
        datetime(2027, 6, 2, 4, 59, 59, tzinfo=timezone.utc),
        datetime(2027, 6, 2, 5, tzinfo=timezone.utc),
    ]
    with database.begin() as db:
        for index, timestamp in enumerate(times):
            db.add(
                AuditEvent(
                    actor_id=uid(2),
                    source="UI",
                    action="calendar_test",
                    resource_type="ticket",
                    outcome="SUCCESS",
                    created_at=timestamp,
                    request_id=f"calendar-{index}",
                    details={},
                )
            )
    events = call(2, "get_recent_activity", start_date=date(2027, 6, 1), end_date=date(2027, 6, 1))[
        "items"
    ]
    assert {event["request_id"] for event in events} == {"calendar-1", "calendar-2"}


def test_inactive_assignees_and_session_identity_cannot_mutate(call, database):
    ticket = call(4, "create_ticket", title="Inactive assignment")
    with database.begin() as db:
        db.get(User, uid(2)).active = False
    with pytest.raises(ServiceError, match="inactive"):
        call(4, "assign_ticket", ticket_id=UUID(ticket["id"]), assignee_id=uid(2))
    with pytest.raises(ServiceError) as error:
        call(2, "create_ticket", title="Inactive actor")
    assert error.value.code == 401
    with database() as db:
        assert db.scalar(select(Ticket).where(Ticket.title == "Inactive actor")) is None
    assert call(4, "get_ticket", ticket_id=UUID(ticket["id"]))["assignee_id"] is None
