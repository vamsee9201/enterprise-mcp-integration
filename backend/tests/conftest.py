import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ["DEMO_MODE"] = "true"

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from backend.app.database.connection import Base
from backend.app.database import connection, seed as seed_module
from backend.app.auth import tokens
from backend.app.api import routes
from backend.app.services import portal
from backend.app.main import app
from backend.app.auth.context import ActorContext
from backend.app.database.seed import uid
from uuid import uuid4


def bind(monkeypatch, engine):
    factory = sessionmaker(engine, expire_on_commit=False)
    for module in (connection, seed_module, tokens, routes, portal):
        monkeypatch.setattr(module, "SessionLocal", factory)
    Base.metadata.create_all(engine)
    seed_module.seed()
    return factory


@pytest.fixture
def database(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")

    factory = bind(monkeypatch, engine)
    yield factory
    engine.dispose()


@pytest.fixture
def call(database):
    def invoke(n, operation_name, **args):
        return portal.run(ActorContext(uid(n), "UI", str(uuid4())), operation_name, **args)

    return invoke


@pytest.fixture
def client(database):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def login(client):
    def perform(n=2):
        r = client.post(
            "/api/v1/auth/demo-login",
            json={"user_id": str(uid(n))},
            headers={"Origin": "http://localhost:3000"},
        )
        assert r.status_code == 200
        client.headers.update(
            {"Origin": "http://localhost:3000", "X-CSRF-Token": r.json()["csrf_token"]}
        )
        return r.json()

    return perform


@pytest.fixture
def postgres_database(monkeypatch):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database")
    if not url.startswith("postgresql") or "test" not in url.rsplit("/", 1)[-1]:
        pytest.fail(
            "TEST_DATABASE_URL must identify a disposable PostgreSQL database with test in its name"
        )
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    factory = bind(monkeypatch, engine)
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()
