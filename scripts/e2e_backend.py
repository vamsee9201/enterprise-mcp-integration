"""Disposable database for browser tests; never touches the development database."""

import os
from pathlib import Path
import sys
import atexit
import subprocess

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from uuid import uuid4
import socket

with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    mcp_port = listener.getsockname()[1]

os.environ.update(
    FIRESTORE_NAMESPACE="test-browser-" + str(uuid4()),
    DEMO_MODE="true",
    WEB_ORIGIN="http://localhost:3020",
    MCP_AUTH_MODE="demo",
    MCP_ALLOWED_HOSTS=f'["127.0.0.1:{mcp_port}"]',
    MCP_RATE_LIMIT="10000",
)
if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
    raise RuntimeError("Browser tests require the Firestore emulator")
from backend.app.database.seed import seed

seed()
import uvicorn
from backend.app.main import app
from backend.app.database.connection import SessionLocal


@app.post("/api/v1/__test/reset", include_in_schema=False)
def reset_browser_fixture():
    # Registered only by this isolated harness, never by the application or Docker.
    # Playwright runs one worker and closes each test's browser context before reset.
    SessionLocal.reset()
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
        str(mcp_port),
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
            f"http://127.0.0.1:{mcp_port}/mcp", *(pair[0] for pair in issued), date(2027, 3, 1)
        )
    finally:
        for _, credential_id in issued:
            revoke_mcp_credential(credential_id)


uvicorn.run(app, host="127.0.0.1", port=8020)
