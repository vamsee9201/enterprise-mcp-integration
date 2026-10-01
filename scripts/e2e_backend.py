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

uvicorn.run("backend.app.main:app", host="127.0.0.1", port=8010)
