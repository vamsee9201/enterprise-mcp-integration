from uuid import UUID
from backend.app.auth.tokens import issue_token, resolve_token
from backend.app.database.seed import seed, uid
from backend.app.models.entities import User, Project, Task, Ticket, TimeEntry


def test_theme_refresh_preserves_existing_workflows(call, database):
    entry = call(
        2,
        "add_time_entry",
        project_id=uid(101),
        work_date="2026-10-01",
        hours=7,
        description="Existing work",
    )
    credential, _ = issue_token(uid(2))
    with database.begin() as db:
        user = db.get(User, uid(2))
        user.name, user.email = "Vamsee Krishna", "vamsee@orbit.example"
        project = db.get(Project, uid(101))
        project.name = "Project Apollo"
        task = db.get(Task, uid(201))
        task.title = "Integrate timesheet MCP tools"
        task.status = "DONE"
        db.get(Task, uid(202)).title = "My edited task"
        ticket = db.get(Ticket, uid(301))
        ticket.title = "My edited ticket"
        ticket.status = "CLOSED"
        ticket.priority = "LOW"
    seed()
    seed()
    with database() as db:
        assert db.get(User, uid(2)).name == "Dinesh Chugtai"
        assert db.get(User, uid(2)).manager_id == uid(1)
        assert db.get(Project, uid(101)).name == "Compression Engine"
        assert db.get(TimeEntry, UUID(entry["id"])).project_id == uid(101)
        assert db.get(Task, uid(201)).title == "Benchmark middle-out compression"
        assert db.get(Task, uid(201)).status == "DONE"
        assert db.get(Task, uid(202)).title == "My edited task"
        assert db.get(Ticket, uid(301)).title == "My edited ticket"
        assert db.get(Ticket, uid(301)).status == "CLOSED"
        assert db.get(Ticket, uid(301)).priority == "LOW"
    assert resolve_token(credential).user_id == uid(2)
    assert call(2, "get_recent_activity")["total"] == 1


def test_seed_without_samples_creates_only_demo_reference_data(database):
    from sqlalchemy import delete, select, func
    from backend.app.models.entities import Membership

    with database.begin() as db:
        for model in (Task, Ticket, Membership, Project, User):
            db.execute(delete(model))
    seed(include_samples=False)
    seed(include_samples=False)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(User)) == 6
        assert db.scalar(select(func.count()).select_from(Project)) == 2
        assert db.scalar(select(func.count()).select_from(Membership)) == 12
        assert db.scalar(select(func.count()).select_from(Task)) == 0
        assert db.scalar(select(func.count()).select_from(Ticket)) == 0
