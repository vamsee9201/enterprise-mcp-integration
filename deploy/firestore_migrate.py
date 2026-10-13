"""One-time protected SQL export and repeatable Firestore import/verification.

SQLAlchemy/psycopg are migration-only dependencies, never installed in runtime.
No credential or record payload is printed. Export files are created mode 0600.
"""

import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from backend.app.database.connection import SessionFactory
from backend.app.models.entities import MODELS


def canonical(data):
    return json.dumps(
        data,
        sort_keys=True,
        default=lambda v: {"__timestamp__": v.isoformat()} if isinstance(v, datetime) else str(v),
    )


def restore(value):
    if isinstance(value, dict):
        if set(value) == {"__timestamp__"}:
            return datetime.fromisoformat(value["__timestamp__"])
        return {k: restore(v) for k, v in value.items()}
    if isinstance(value, list):
        return [restore(v) for v in value]
    return value


def export_sql(output, url_file):
    from sqlalchemy import create_engine, text, inspect

    engine = create_engine(Path(url_file).read_text().strip())
    data = {}
    with engine.connect() as db:
        with db.begin():
            db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            tables = set(inspect(db).get_table_names())
            for model in MODELS:
                if model.collection == "chat_conversations" and model.collection not in tables:
                    data[model.collection] = []
                    continue
                rows = db.execute(text(f'SELECT * FROM "{model.collection}"')).mappings()
                data[model.collection] = [model(**dict(row)).document() for row in rows]
    engine.dispose()
    raw = canonical(data)
    envelope = canonical({"sha256": hashlib.sha256(raw.encode()).hexdigest(), "collections": data})
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as file:
        file.write(envelope)
    print(json.dumps({name: len(rows) for name, rows in data.items()}))


def validate(data):
    ids = {name: {row.get("id") for row in rows} for name, rows in data.items()}
    seen = set()
    for name, rows in data.items():
        for row in rows:
            for field, target in [
                ("user_id", "users"),
                ("manager_id", "users"),
                ("creator_id", "users"),
                ("assignee_id", "users"),
                ("reviewer_id", "users"),
                ("actor_id", "users"),
                ("project_id", "projects"),
                ("timesheet_id", "timesheets"),
            ]:
                if row.get(field) and row[field] not in ids[target]:
                    raise ValueError(f"Broken {name}.{field} reference")
            if name == "timesheets":
                key = (row["user_id"], row["week_start"])
                if key in seen:
                    raise ValueError("Duplicate employee week")
                seen.add(key)
    return {name: len(rows) for name, rows in data.items()}


def import_export(source, namespace, verify_only=False):
    envelope = json.loads(source.read_text())
    if (
        hashlib.sha256(canonical(restore(envelope["collections"])).encode()).hexdigest()
        != envelope["sha256"]
    ):
        raise ValueError("Export checksum mismatch")
    data = restore(envelope["collections"])
    counts = validate(data)
    factory = SessionFactory(namespace=namespace)
    if not verify_only:
        for model in MODELS:
            for row in data[model.collection]:
                # One record per transaction keeps history imports under transaction limits.
                def put(row=row, model=model):
                    with factory() as db:
                        obj = model.from_document(row)
                        old = db.get(model, db.key(obj))
                        if old:
                            for name in model.fields:
                                setattr(old, name, getattr(obj, name))
                        else:
                            db.add(obj)

                factory.atomic(put)
    with factory() as db:
        from backend.app.database.query import select

        for model in MODELS:
            actual = sorted((obj.document() for obj in db.scalars(select(model))), key=canonical)
            expected = sorted(data[model.collection], key=canonical)
            if canonical(actual) != canonical(expected):
                raise ValueError(f"Verification mismatch: {model.collection}")
    print(json.dumps({"verified": True, "counts": counts, "sha256": envelope["sha256"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["export", "import", "verify"])
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--url-file", type=Path)
    parser.add_argument("--namespace", default="portal")
    args = parser.parse_args()
    if args.command == "export":
        export_sql(args.file, args.url_file)
    else:
        import_export(args.file, args.namespace, args.command == "verify")
