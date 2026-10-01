from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func
from backend.app.auth.context import ActorContext, ServiceError
from backend.app.database.seed import uid
from backend.app.models.entities import TimeEntry, AuditEvent
from backend.app.services.portal import run

pytestmark = pytest.mark.postgres


def invoke(n, action, **args):
    return run(ActorContext(uid(n), "UI", str(uuid4())), action, **args)


def race(operations):
    barrier = Barrier(len(operations))

    def execute(op):
        barrier.wait()
        try:
            return op()
        except ServiceError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=len(operations)) as pool:
        return list(pool.map(execute, operations))


def test_concurrent_approval_has_one_winner(postgres_database):
    invoke(
        2,
        "add_time_entry",
        project_id=uid(101),
        work_date=date(2026, 9, 30),
        hours=7,
        description="Work",
    )
    sheet = invoke(2, "submit_timesheet", week=date(2026, 9, 30))
    results = race(
        [
            lambda: invoke(1, "approve_timesheet", timesheet_id=UUID(sheet["id"])),
            lambda: invoke(
                6, "reject_timesheet", timesheet_id=UUID(sheet["id"]), reason="Needs correction"
            ),
        ]
    )
    assert sum(isinstance(r, dict) for r in results) == 1
    assert results.count(409) == 1
    with postgres_database() as db:
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


def test_concurrent_daily_hours_and_sheet_creation(postgres_database):
    results = race(
        [
            lambda: invoke(
                2,
                "add_time_entry",
                project_id=uid(101),
                work_date=date(2026, 9, 30),
                hours=14,
                description="Work",
            )
            for _ in range(2)
        ]
    )
    assert sum(isinstance(r, dict) for r in results) == 1 and results.count(422) == 1
    with postgres_database() as db:
        assert db.scalar(select(func.sum(TimeEntry.hours))) == 14


def test_concurrent_overlapping_leave(postgres_database):
    results = race(
        [
            lambda: invoke(
                2, "request_leave", start_date=date(2026, 10, 12), end_date=date(2026, 10, 14)
            )
            for _ in range(2)
        ]
    )
    assert sum(isinstance(r, dict) for r in results) == 1 and results.count(409) == 1
