from datetime import date
from decimal import Decimal
from uuid import uuid4
import pytest
from backend.app.database.connection import IntegrityError
from backend.app.database.query import select
from backend.app.database.seed import uid
from backend.app.models.entities import ChatConversation, Timesheet, TimeEntry, AuditEvent
from deploy.firestore_migrate import canonical, import_export
import hashlib
import json


def test_week_uniqueness_is_transactional(database):
    with database.begin() as db:
        db.add(Timesheet(user_id=uid(2), week_start=date(2026, 10, 12)))
    with pytest.raises(IntegrityError):
        database.atomic(
            lambda: database().add(Timesheet(user_id=uid(2), week_start=date(2026, 10, 12)))
        )
    with database() as db:
        assert len(db.scalars(select(Timesheet))) == 1


def test_chat_payloads_use_subcollections(database):
    cid = uuid4()
    with database.begin() as db:
        db.add(
            ChatConversation(
                id=cid,
                user_id=uid(2),
                messages=[{"role": "user", "text": "Hello"}],
                events=[{"context": "safe"}],
                results={"turn": {"input": "Hello"}},
            )
        )
    parent = database.root.collection("chat_conversations").document(str(cid))
    assert not {"messages", "events", "results"} & parent.get().to_dict().keys()
    assert len(list(parent.collection("messages").stream())) == 1
    with database() as db:
        saved = db.get(ChatConversation, cid)
        assert saved.messages == [{"role": "user", "text": "Hello"}]
        assert saved.results["turn"]["input"] == "Hello"


def test_failed_transaction_leaves_no_business_or_audit(database):
    def fail():
        with database() as db:
            db.add(
                TimeEntry(
                    timesheet_id=uuid4(),
                    project_id=uid(101),
                    work_date=date(2026, 10, 12),
                    hours=Decimal("0.01"),
                    description="",
                )
            )
            db.add(
                AuditEvent(
                    actor_id=uid(2),
                    source="MCP",
                    action="test",
                    resource_type="entry",
                    resource_id="test",
                    outcome="SUCCESS",
                    request_id="test",
                )
            )
            raise RuntimeError("Injected worker failure")

    with pytest.raises(RuntimeError):
        database.atomic(fail)
    with database() as db:
        assert db.scalars(select(TimeEntry)) == []
        assert db.scalars(select(AuditEvent)) == []


def test_migration_checksum_rejects_modified_export(tmp_path):
    source = tmp_path / "export.json"
    source.write_text(json.dumps({"sha256": "wrong", "collections": {}}))
    with pytest.raises(ValueError, match="checksum"):
        import_export(source, "test-never-written")
    assert hashlib.sha256(canonical({}).encode()).hexdigest() != "wrong"


def test_cold_start_initializes_one_factory(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import time
    from backend.app.database import connection

    calls = []

    class Factory:
        def __init__(self):
            time.sleep(0.01)
            calls.append(self)

        def __call__(self):
            return self

    monkeypatch.setattr(connection, "SessionFactory", Factory)
    lazy = connection.LazyFactory()
    with ThreadPoolExecutor(max_workers=8) as pool:
        instances = list(pool.map(lambda _: lazy(), range(8)))
    assert len(calls) == 1
    assert all(instance is instances[0] for instance in instances)
