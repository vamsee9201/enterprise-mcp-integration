"""Disposable database for browser tests; never touches the development database."""

import os
from pathlib import Path
import sys
import tempfile
import atexit
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
fd, filename = tempfile.mkstemp(prefix="orbit-browser-", suffix=".db")
os.close(fd)
atexit.register(lambda: Path(filename).unlink(missing_ok=True))
os.environ.update(
    DATABASE_URL=f"sqlite:///{filename}", DEMO_MODE="true", WEB_ORIGIN="http://localhost:3010"
)
subprocess.run(
    [sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"],
    check=True,
    cwd=Path(__file__).resolve().parents[1],
)
from backend.app.database.seed import seed

seed()
import uvicorn
from backend.app.main import app
from backend.app.database.connection import Base, engine


@app.post("/api/v1/__test/reset", include_in_schema=False)
def reset_browser_fixture():
    # Registered only by this isolated harness, never by the application or Docker.
    # Playwright runs one worker and closes each test's browser context before reset.
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
    seed()
    return {"ok": True}


uvicorn.run(app, host="127.0.0.1", port=8010)
