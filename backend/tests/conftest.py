import os

os.environ["DEMO_MODE"] = "true"

import pytest
from fastapi.testclient import TestClient
from backend.app.database.connection import SessionFactory
from backend.app.database import connection, seed as seed_module
from backend.app.auth import tokens
from backend.app.api import routes
from backend.app.services import portal
from backend.app.main import app
from backend.app.auth.context import ActorContext
from backend.app.database.seed import uid
from uuid import uuid4


def bind(monkeypatch, factory):
    from backend.app import main

    for module in (connection, seed_module, tokens, routes, portal, main):
        monkeypatch.setattr(module, "SessionLocal", factory)
    seed_module.seed()
    return factory


@pytest.fixture
def database(monkeypatch):
    if not os.environ.get("FIRESTORE_EMULATOR_HOST") and not os.environ.get("FIRESTORE_LIVE_TESTS"):
        pytest.fail("Start Firestore emulator and set FIRESTORE_EMULATOR_HOST")
    factory = bind(monkeypatch, SessionFactory(namespace="test-" + str(uuid4())))
    yield factory
    factory.reset()


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
def firestore_database(database):
    return database
