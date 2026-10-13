"""Request-local Firestore units of work with retryable, atomic commits.

Writes are buffered until all business reads have completed. The transaction
callback may be re-executed; network/model side effects must stay outside it.
"""

import hashlib
import logging
import os
from contextvars import ContextVar
from functools import wraps
from threading import Lock
from copy import deepcopy
from uuid import UUID
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.api_core.exceptions import Aborted, Conflict
from backend.app.config import settings
from backend.app.database.query import Aggregate, Field, Predicate, Query

active_session = ContextVar("firestore_session", default=None)


class IntegrityError(Exception):
    pass


def encode(value):
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return int(value * 100)
    return value


class DocumentSession:
    def __init__(self, factory, transaction=None):
        self.factory, self.transaction = factory, transaction
        self.cache, self.original, self.new, self.deleted = {}, {}, set(), set()
        self.guards = {}
        self.reads = 0
        self.writes = 0

    def __enter__(self):
        return self

    def __exit__(self, kind, error, tb):
        if kind:
            self.rollback()

    def ref(self, model, key):
        return self.factory.root.collection(model.collection).document(str(key))

    def key(self, obj):
        if obj.collection == "project_memberships":
            return f"{obj.project_id}_{obj.user_id}"
        if obj.collection == "idempotency_records":
            return hashlib.sha256(f"{obj.actor_id}:{obj.operation}:{obj.key}".encode()).hexdigest()
        return str(obj.id)

    def get(self, model, key):
        if isinstance(key, tuple):
            key = "_".join(map(str, key))
        slot = (model, str(key))
        if slot in self.deleted:
            return None
        if slot in self.cache:
            return self.cache[slot]
        self.reads += 1
        snapshot = self.ref(model, key).get(transaction=self.transaction)
        return self.remember(model, snapshot) if snapshot.exists else None

    def remember(self, model, snapshot):
        slot = (model, snapshot.id)
        if slot in self.cache:
            return self.cache[slot]
        data = snapshot.to_dict()
        if model.collection == "chat_conversations":
            for name in ("messages", "events", "results"):
                parts = list(
                    snapshot.reference.collection(name).stream(transaction=self.transaction)
                )
                self.reads += max(1, len(parts))
                if name == "results":
                    data[name] = {p.id: p.to_dict()["value"] for p in parts}
                else:
                    data[name] = [p.to_dict()["value"] for p in sorted(parts, key=lambda p: p.id)]
        obj = model.from_document(data)
        self.cache[slot], self.original[slot] = obj, deepcopy(obj.document())
        return obj

    def guard(self, employee_id):
        key = str(employee_id)
        if key not in self.guards:
            ref = self.factory.root.collection("guards").document(key)
            self.reads += 1
            snap = ref.get(transaction=self.transaction)
            self.guards[key] = (ref, (snap.to_dict() or {}).get("version", 0) + 1)

    def add(self, obj):
        slot = (type(obj), self.key(obj))
        if slot not in self.original:
            if self.get(type(obj), slot[1]) is not None:
                raise IntegrityError("Duplicate document")
            self.new.add(slot)
        self.cache[slot] = obj

    def add_all(self, records):
        for obj in records:
            self.add(obj)

    def delete(self, obj):
        self.deleted.add((type(obj), self.key(obj)))

    def flush(self):
        # IDs/defaults are assigned at construction, not at commit.
        pass

    def objects(self, query):
        collection = self.factory.root.collection(query.model.collection)
        # One equality/indexed membership filter avoids composite-index requirements.
        # Empty membership is evaluated locally; never issue an invalid Firestore IN.
        for p in query.predicates:
            if isinstance(p, Predicate) and p.op == "==" and p.field.name == "id":
                obj = self.get(query.model, p.value)
                return (
                    [obj]
                    if obj and all(check.matches(obj, self) for check in query.predicates)
                    else []
                )
        for p in query.predicates:
            if isinstance(p, Predicate) and not isinstance(p.value, Query) and p.op in ("==", "in"):
                value = [encode(v) for v in p.value] if p.op == "in" else encode(p.value)
                if p.field.name != "id" and (p.op != "in" or 0 < len(value) <= 30):
                    collection = collection.where(
                        filter=FieldFilter(p.field.name, "in" if p.op == "in" else "==", value)
                    )
                    break
        records = {}
        snapshots = list(collection.stream(transaction=self.transaction))
        self.reads += max(1, len(snapshots))
        for snap in snapshots:
            slot = (query.model, snap.id)
            if slot not in self.deleted:
                records[snap.id] = self.remember(query.model, snap)
        for (model, key), obj in self.cache.items():
            if model is query.model and (model, key) not in self.deleted:
                records[key] = obj
        result = [
            obj for obj in records.values() if all(p.matches(obj, self) for p in query.predicates)
        ]
        # UUID tie-break makes pages deterministic across storage enumeration order.
        result.sort(key=lambda obj: str(getattr(obj, "id", self.key(obj))))
        for field in reversed(query.orders):
            field, reverse = field if isinstance(field, tuple) else (field, False)
            result.sort(
                key=lambda obj: (getattr(obj, field.name) is not None, getattr(obj, field.name)),
                reverse=reverse,
            )
        return result

    def scalars(self, query):
        records = self.objects(query)
        records = records[
            query.skip : query.skip + query.maximum if query.maximum is not None else None
        ]
        return (
            [getattr(o, query.target.name) for o in records]
            if isinstance(query.target, Field)
            else records
        )

    def scalar(self, query):
        if isinstance(query.target, Aggregate):
            records = self.objects(query.source or query)
            if query.target.kind == "count":
                return len(records)
            return (
                sum(getattr(o, query.target.field.name) for o in records)
                if records
                else query.target.fallback
            )
        records = self.scalars(query)
        return records[0] if records else None

    def execute(self, query):
        from backend.app.database.query import Delete

        if not isinstance(query, Delete):
            raise TypeError("Only document deletion queries are supported")
        for obj in self.objects(query):
            self.delete(obj)

    def rollback(self):
        self.cache.clear()
        self.original.clear()
        self.new.clear()
        self.deleted.clear()
        self.guards.clear()

    def commit(self):
        # Joined sessions commit only at the end of the outer retryable operation.
        if active_session.get() is self:
            return
        self.persist()
        self.rollback()

    def persist(self):
        unique_writes = []
        for slot, obj in self.cache.items():
            if slot not in self.new or slot in self.deleted or obj.collection != "timesheets":
                continue
            unique = self.factory.root.collection("timesheet_weeks").document(
                f"{obj.user_id}_{obj.week_start}"
            )
            self.reads += 1
            snapshot = unique.get(transaction=self.transaction)
            if snapshot.exists and snapshot.to_dict()["id"] != str(obj.id):
                raise IntegrityError("Duplicate employee week")
            if slot in self.new:
                unique_writes.append((unique, {"id": str(obj.id)}))
        writer = self.transaction if self.transaction is not None else self.factory.client.batch()
        session = self
        delegate = writer

        class Writer:
            def __getattr__(self, name):
                method = getattr(delegate, name)
                if name not in ("set", "create", "delete"):
                    return method

                def counted(*args, **kwargs):
                    session.writes += 1
                    return method(*args, **kwargs)

                return counted

        writer = Writer()
        for ref, values in unique_writes:
            writer.set(ref, values)
        for key, (ref, version) in self.guards.items():
            writer.set(ref, {"version": version})
        for model, key in self.deleted:
            writer.delete(self.ref(model, key))
        for slot, obj in self.cache.items():
            if slot in self.deleted:
                continue
            data = obj.document()
            if slot not in self.new and data == self.original.get(slot):
                continue
            ref = self.ref(*slot)
            if obj.collection == "chat_conversations":
                before = self.original.get(slot, {})
                for name in ("messages", "events", "results"):
                    values = data.pop(name)
                    old = before.get(name, {} if name == "results" else [])
                    items = (
                        values.items()
                        if isinstance(values, dict)
                        else ((f"{i:08d}", v) for i, v in enumerate(values))
                    )
                    for part_key, value in items:
                        previous = (
                            old.get(part_key)
                            if isinstance(old, dict)
                            else old[int(part_key)]
                            if int(part_key) < len(old)
                            else None
                        )
                        if value != previous:
                            writer.set(
                                ref.collection(name).document(str(part_key)), {"value": value}
                            )
                    old_keys = (
                        set(old) if isinstance(old, dict) else {f"{i:08d}" for i in range(len(old))}
                    )
                    new_keys = (
                        set(values)
                        if isinstance(values, dict)
                        else {f"{i:08d}" for i in range(len(values))}
                    )
                    for removed in old_keys - new_keys:
                        writer.delete(ref.collection(name).document(removed))
            if slot in self.new:
                writer.create(ref, data)
            else:
                writer.set(ref, data)
        if self.transaction is None:
            writer.commit()


class SessionFactory:
    def __init__(self, namespace=None, client=None):
        self.namespace = namespace or settings.firestore_namespace
        self.client = client or firestore.Client(
            project=settings.firestore_project, database=settings.firestore_database
        )
        self.root = self.client.collection("enterprise_workspaces").document(self.namespace)

    def __call__(self):
        existing = active_session.get()
        return existing if existing and existing.factory is self else DocumentSession(self)

    def begin(self):
        factory = self

        class Begin:
            def __enter__(self):
                self.joined = active_session.get()
                self.session = factory()
                return self.session

            def __exit__(self, kind, error, tb):
                if kind:
                    self.session.rollback()
                elif not self.joined:
                    self.session.commit()

        return Begin()

    def atomic(self, callback):
        transaction = self.client.transaction(max_attempts=8)
        attempts = []

        @firestore.transactional
        def execute(tx):
            session = DocumentSession(self, tx)
            marker = active_session.set(session)
            try:
                result = callback()
                active_session.reset(marker)
                marker = None
                session.persist()
                attempts.append({"reads": session.reads, "writes": session.writes})
                return result
            finally:
                if marker is not None:
                    active_session.reset(marker)

        try:
            result = execute(transaction)
            logging.getLogger("portal.firestore").info(
                "operation_io namespace=%s attempts=%d document_reads=%d document_writes=%d",
                self.namespace,
                len(attempts),
                sum(a["reads"] for a in attempts),
                sum(a["writes"] for a in attempts),
            )
            return result
        except (Aborted, Conflict, ValueError) as exc:
            if isinstance(exc, ValueError) and not isinstance(exc.__cause__, Aborted):
                raise
            from backend.app.auth.context import ServiceError

            raise ServiceError("Record changed concurrently; refresh and retry", 409) from exc

    def reset(self):
        if not os.environ.get("FIRESTORE_EMULATOR_HOST") and not self.namespace.startswith("test-"):
            raise RuntimeError("Reset requires emulator or explicitly isolated test namespace")
        self.client.recursive_delete(self.root)


def atomic(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if active_session.get():
            return fn(*args, **kwargs)
        return SessionLocal.atomic(lambda: fn(*args, **kwargs))

    return wrapped


# Lazy initialization keeps imports independent of cloud credentials.
class LazyFactory:
    _factory = None
    _lock = Lock()

    def __getattr__(self, name):
        if self._factory is None:
            with self._lock:
                if self._factory is None:
                    self._factory = SessionFactory()
        return getattr(self._factory, name)

    def __call__(self):
        return self.__getattr__("__call__")()


SessionLocal = LazyFactory()
