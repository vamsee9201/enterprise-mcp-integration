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
        name="Bertram Gilfoyle",
        email="gilfoyle@piedpiper.example",
        role="MANAGER",
        department="Engineering",
        manager_id=None,
    ),
    dict(
        id=uid(2),
        name="Dinesh Chugtai",
        email="dinesh@piedpiper.example",
        role="EMPLOYEE",
        department="Engineering",
        manager_id=uid(1),
    ),
    dict(
        id=uid(3),
        name="Jared Dunn",
        email="jared@piedpiper.example",
        role="EMPLOYEE",
        department="Operations",
        manager_id=uid(1),
    ),
    dict(
        id=uid(4),
        name="Monica Hall",
        email="monica@piedpiper.example",
        role="MANAGER",
        department="Business Operations",
        manager_id=None,
    ),
    dict(
        id=uid(5),
        name="Erlich Bachman",
        email="erlich@piedpiper.example",
        role="EMPLOYEE",
        department="Business Operations",
        manager_id=uid(4),
    ),
    dict(
        id=uid(6),
        name="Richard Hendricks",
        email="richard@piedpiper.example",
        role="ADMIN",
        department="Leadership",
        manager_id=None,
    ),
]


PROJECTS = [
    (
        101,
        "Compression Engine",
        "Develop and benchmark Pied Piper’s middle-out compression engine.",
    ),
    (102, "PiperNet", "Build and harden Pied Piper’s decentralized network platform."),
]


def refresh_sample(record, fields):
    """Upgrade untouched old seed text without replacing user edits or workflow state."""
    for key, (legacy, themed) in fields.items():
        if getattr(record, key) == legacy:
            setattr(record, key, themed)


def seed(include_samples=True):
    today = datetime.now(ZoneInfo(settings.app_timezone)).date()
    with SessionLocal.begin() as db:
        for data in USERS:
            user = db.get(User, data["id"])
            if user is None:
                db.add(User(**data))
            else:
                for field in ("name", "email", "department"):
                    setattr(user, field, data[field])
            db.flush()
        for n, name, description in PROJECTS:
            project = db.get(Project, uid(n))
            if project is None:
                db.add(Project(id=uid(n), name=name, description=description))
            else:
                project.name, project.description = name, description
            db.flush()
            for data in USERS:
                if not db.get(Membership, (uid(n), data["id"])):
                    db.add(Membership(project_id=uid(n), user_id=data["id"]))

        if not include_samples:
            return

        samples = [
            (
                201,
                "Benchmark middle-out compression",
                "Compare compression ratios and latency against the baseline dataset.",
                2,
                3,
                "IN_PROGRESS",
                "Integrate timesheet MCP tools",
                "Connect the shared services and verify audit source attribution.",
            ),
            (
                202,
                "Prepare PiperNet launch checklist",
                "Coordinate the rollout checklist, team handoffs and launch readiness.",
                3,
                5,
                "TODO",
                "Review permission boundaries",
                "Check employee and manager access across workflows.",
            ),
        ]
        for n, title, description, assignee, days, status, old_title, old_description in samples:
            task = db.get(Task, uid(n))
            if task is None:
                db.add(
                    Task(
                        id=uid(n),
                        title=title,
                        description=description,
                        project_id=uid(101 if n == 201 else 102),
                        creator_id=uid(1),
                        assignee_id=uid(assignee),
                        due_date=today + timedelta(days=days),
                        status=status,
                    )
                )
            else:
                refresh_sample(
                    task,
                    {"title": (old_title, title), "description": (old_description, description)},
                )

        ticket = db.get(Ticket, uid(301))
        title = "PiperNet staging VPN disconnects"
        description = "The staging VPN disconnects during compression benchmark uploads. Please investigate network access."
        if ticket is None:
            db.add(
                Ticket(
                    id=uid(301),
                    title=title,
                    description=description,
                    creator_id=uid(2),
                    assignee_id=uid(1),
                    priority="HIGH",
                    status="IN_PROGRESS",
                )
            )
        else:
            refresh_sample(
                ticket,
                {
                    "title": ("VPN connection drops intermittently", title),
                    "description": (
                        "Connection drops when switching networks. Please investigate.",
                        description,
                    ),
                },
            )
