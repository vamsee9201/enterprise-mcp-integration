import os
from uuid import UUID, uuid4

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.auth import tokens
from backend.app.config import settings
from backend.app.database.connection import Base
from backend.app.database import seed
from backend.app.database.seed import uid
from backend.app.models.entities import ChatConversation, SessionToken
from chat_app import main
from chat_app.agent import tool_outcome


@pytest.mark.parametrize(
    "response,expected",
    [
        ({"isError": True}, "Denied or failed"),
        ({"is_error": True}, "Denied or failed"),
        ({"error": "Transport failure"}, "Denied or failed"),
        (
            {"isError": False, "content": [{"text": 'description says "isError": true'}]},
            "Completed",
        ),
    ],
)
def test_action_status_matches_real_tool_outcome(response, expected):
    assert tool_outcome(response) == expected


@pytest.fixture
def client(tmp_path, monkeypatch):
    engine = create_engine(
        f"sqlite:///{tmp_path}/chat.db", connect_args={"check_same_thread": False}
    )
    factory = sessionmaker(engine, expire_on_commit=False)
    for module in (main, tokens, seed):
        monkeypatch.setattr(module, "SessionLocal", factory)
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "secure_cookies", False)
    Base.metadata.create_all(engine)
    seed.seed(include_samples=False)
    calls = []

    async def fake_agent(profile, events, message, turn_id):
        calls.append(profile)
        return {
            "events": [],
            "message": {"role": "assistant", "text": profile["name"], "actions": []},
        }

    monkeypatch.setattr(main, "run_agent", fake_agent)
    with TestClient(main.app) as c:
        c.headers["Origin"] = "http://localhost:3400"
        c.factory, c.calls = factory, calls
        yield c
    engine.dispose()


def login(client, number=2):
    response = client.post("/chat/login", json={"profile_id": str(uid(number))})
    assert response.status_code == 200
    return response.json()


def send(client, session, number=2, turn=None, text="Show my work"):
    return client.post(
        f"/chat/message/{uid(number)}",
        json={"text": text, "turn_id": str(turn or uuid4())},
        headers={"X-CSRF-Token": session["csrf_token"]},
    )


def test_profiles_and_allowlisted_login(client):
    assert len(client.get("/chat/profiles").json()["profiles"]) == 6
    assert client.post("/chat/login", json={"profile_id": str(uuid4())}).status_code == 403
    assert (
        client.post("/chat/login", json={"profile_id": str(uid(2)), "role": "ADMIN"}).status_code
        == 422
    )


def test_profile_credentials_stay_in_httponly_cookie(client):
    r = client.post("/chat/login", json={"profile_id": str(uid(2))})
    assert "HttpOnly" in r.headers["set-cookie"] and "SameSite=strict" in r.headers["set-cookie"]
    assert "token" not in r.json()
    session = r.json()
    assert send(client, session).status_code == 200
    assert client.calls[0]["role"] == "EMPLOYEE"
    assert client.get(f"/chat/session/{uid(2)}").json()["messages"][1]["text"] == "Dinesh Chugtai"


def test_persona_sessions_and_history_are_isolated(client):
    dinesh = login(client, 2)
    richard = login(client, 6)
    assert send(client, dinesh, 6).status_code == 403
    assert send(client, dinesh, 2).status_code == 200
    assert send(client, richard, 6).status_code == 200
    assert [p["role"] for p in client.calls] == ["EMPLOYEE", "ADMIN"]
    assert client.get(f"/chat/session/{uid(2)}").json()["messages"][1]["text"] == "Dinesh Chugtai"
    assert (
        client.get(f"/chat/session/{uid(6)}").json()["messages"][1]["text"] == "Richard Hendricks"
    )


def test_origin_csrf_and_kind_boundaries(client):
    session = login(client)
    client.headers["Origin"] = "https://evil.example"
    assert send(client, session).status_code == 403
    assert client.post("/chat/login", json={"profile_id": str(uid(6))}).status_code == 403
    client.headers["Origin"] = "http://localhost:3400"
    assert (
        client.post(
            f"/chat/message/{uid(2)}", json={"text": "Hello", "turn_id": str(uuid4())}
        ).status_code
        == 403
    )
    with client.factory.begin() as db:
        db.get(SessionToken, UUID(session["conversation_id"])).kind = "WEB"
    assert client.get(f"/chat/session/{uid(2)}").status_code == 401


def test_turn_retries_do_not_repeat_agent_actions(client):
    session, key = login(client), uuid4()
    assert send(client, session, turn=key).json()["replayed"] is False
    assert send(client, session, turn=key).json()["replayed"] is True
    assert len(client.calls) == 1
    assert send(client, session, turn=key, text="Different write").status_code == 409


def test_interrupted_turn_does_not_silently_rerun(client):
    session = login(client)
    with client.factory.begin() as db:
        from backend.app.models.entities import utcnow

        db.get(ChatConversation, UUID(session["conversation_id"])).busy_until = utcnow()
    assert send(client, session).status_code == 409
    assert not client.calls


def test_logout_rejects_session_and_new_chat_has_empty_history(client):
    session = login(client)
    assert send(client, session).status_code == 200
    fresh = login(client)
    assert fresh["messages"] == [] and fresh["conversation_id"] != session["conversation_id"]
    assert (
        client.post(
            f"/chat/logout/{uid(2)}", headers={"X-CSRF-Token": fresh["csrf_token"]}
        ).status_code
        == 200
    )
    assert client.get(f"/chat/session/{uid(2)}").status_code == 401


def test_failed_turn_is_saved_and_not_replayed(client, monkeypatch):
    async def fail(*args):
        raise RuntimeError("Secret exception must never reach the browser")

    monkeypatch.setattr(main, "run_agent", fail)
    session, key = login(client), uuid4()
    response = send(client, session, turn=key)
    assert response.status_code == 200 and response.json()["message"]["failed"]
    assert "Secret exception" not in response.text
    assert send(client, session, turn=key).json()["replayed"]


@pytest.mark.postgres
def test_concurrent_turns_are_serialized(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from fastapi import HTTPException

    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL test database")
    assert url.startswith("postgresql") and "test" in url.rsplit("/", 1)[-1]
    engine = create_engine(url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(seed, "SessionLocal", factory)
    monkeypatch.setattr(main, "SessionLocal", factory)
    seed.seed(include_samples=False)
    conversation_id = uuid4()
    with factory.begin() as db:
        db.add(ChatConversation(id=conversation_id, user_id=uid(2)))
    barrier = Barrier(2)

    def submit():
        barrier.wait()
        try:
            main.start_turn(conversation_id, uid(2), main.Message(text="Log time", turn_id=uuid4()))
            return 200
        except HTTPException as error:
            return error.status_code

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(lambda _: submit(), range(2))) == [200, 409]
        with factory() as db:
            assert len(db.get(ChatConversation, conversation_id).messages) == 1
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
