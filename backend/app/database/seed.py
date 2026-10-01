"""Idempotent seed data. Never resets existing workflow records."""

from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo
from backend.app.config import settings
from backend.app.database.connection import SessionLocal
from backend.app.models.entities import User, Project, Membership, Task, Ticket


def uid(n):
    return UUID(f"00000000-0000-4000-8000-{n:012d}")


USERS = [
    dict(
        id=uid(1),
        name="Maya Chen",
        email="maya@orbit.example",
        role="MANAGER",
        department="Engineering",
        manager_id=None,
    ),
    dict(
        id=uid(2),
        name="Vamsee Krishna",
        email="vamsee@orbit.example",
        role="EMPLOYEE",
        department="Engineering",
        manager_id=uid(1),
    ),
    dict(
        id=uid(3),
        name="Alex Morgan",
        email="alex@orbit.example",
        role="EMPLOYEE",
        department="Engineering",
        manager_id=uid(1),
    ),
    dict(
        id=uid(4),
        name="Jordan Lee",
        email="jordan@orbit.example",
        role="MANAGER",
        department="Operations",
        manager_id=None,
    ),
    dict(
        id=uid(5),
        name="Sam Rivera",
        email="sam@orbit.example",
        role="EMPLOYEE",
        department="Operations",
        manager_id=uid(4),
    ),
    dict(
        id=uid(6),
        name="Avery Patel",
        email="avery@orbit.example",
        role="ADMIN",
        department="IT Administration",
        manager_id=None,
    ),
]


def seed():
    today = datetime.now(ZoneInfo(settings.app_timezone)).date()
    with SessionLocal.begin() as db:
        for data in USERS:
            if not db.get(User, data["id"]):
                db.add(User(**data))
                db.flush()
        for n, name, description in [
            (101, "Project Apollo", "Connect enterprise workflows to AI agents through MCP."),
            (102, "Platform Modernization", "Improve the internal operations platform."),
        ]:
            if not db.get(Project, uid(n)):
                db.add(Project(id=uid(n), name=name, description=description))
                db.flush()
            for data in USERS:
                if not db.get(Membership, (uid(n), data["id"])):
                    db.add(Membership(project_id=uid(n), user_id=data["id"]))
        if not db.get(Task, uid(201)):
            db.add(
                Task(
                    id=uid(201),
                    title="Integrate timesheet MCP tools",
                    description="Connect the shared services and verify audit source attribution.",
                    project_id=uid(101),
                    creator_id=uid(1),
                    assignee_id=uid(2),
                    due_date=today + timedelta(days=3),
                    status="IN_PROGRESS",
                )
            )
            db.add(
                Task(
                    id=uid(202),
                    title="Review permission boundaries",
                    description="Check employee and manager access across workflows.",
                    project_id=uid(101),
                    creator_id=uid(1),
                    assignee_id=uid(3),
                    due_date=today + timedelta(days=5),
                    status="TODO",
                )
            )
        if not db.get(Ticket, uid(301)):
            db.add(
                Ticket(
                    id=uid(301),
                    title="VPN connection drops intermittently",
                    description="Connection drops when switching networks. Please investigate.",
                    creator_id=uid(2),
                    assignee_id=uid(6),
                    priority="HIGH",
                    status="IN_PROGRESS",
                )
            )
