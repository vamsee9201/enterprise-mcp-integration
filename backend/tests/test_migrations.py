import os
import subprocess
import sys
from sqlalchemy import create_engine, inspect


def test_migration_upgrade_downgrade(tmp_path):
    url = f"sqlite:///{tmp_path}/migration.db"
    env = {**os.environ, "DATABASE_URL": url}
    command = [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini"]
    subprocess.run([*command, "upgrade", "head"], env=env, check=True)
    engine = create_engine(url)
    assert {
        "users",
        "timesheets",
        "time_entries",
        "tasks",
        "leave_requests",
        "tickets",
        "audit_events",
    } <= set(inspect(engine).get_table_names())
    engine.dispose()
    subprocess.run([*command, "downgrade", "base"], env=env, check=True)
    engine = create_engine(url)
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()
