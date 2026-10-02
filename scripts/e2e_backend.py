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
    DATABASE_URL=f"sqlite:///{filename}",
    DEMO_MODE="true",
    WEB_ORIGIN="http://localhost:3010",
    MCP_AUTH_MODE="demo",
    MCP_ALLOWED_HOSTS='["127.0.0.1:8011"]',
    MCP_RATE_LIMIT="10000",
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


mcp_process = subprocess.Popen(
    [
        sys.executable,
        "-m",
        "uvicorn",
        "mcp_server.asgi:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8011",
        "--log-level",
        "error",
    ]
)


def stop_mcp():
    mcp_process.terminate()
    try:
        mcp_process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        mcp_process.kill()
        mcp_process.wait()


atexit.register(stop_mcp)


@app.post("/api/v1/__test/mcp-demo", include_in_schema=False)
async def browser_mcp_demo():
    from datetime import date
    from backend.app.auth.tokens import issue_mcp_token, revoke_mcp_credential
    from backend.app.database.seed import uid
    from scripts.mcp_demo import demonstrate

    issued = [
        issue_mcp_token(
            uid(n),
            ["portal:read", "portal:write", "portal:review"]
            if n != 2
            else ["portal:read", "portal:write"],
        )
        for n in (2, 1, 6)
    ]
    try:
        return await demonstrate(
            "http://127.0.0.1:8011/mcp", *(pair[0] for pair in issued), date(2027, 3, 1)
        )
    finally:
        for _, credential_id in issued:
            revoke_mcp_credential(credential_id)


uvicorn.run(app, host="127.0.0.1", port=8010)
