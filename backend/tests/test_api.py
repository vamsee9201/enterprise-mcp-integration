import pytest
from datetime import timedelta
from sqlalchemy import select
from backend.app.database.seed import uid
from backend.app.models.entities import SessionToken, utcnow
from backend.app.config import settings


def test_session_csrf_origin_and_logout(client, login, database):
    assert client.get("/api/v1/tasks").status_code == 401
    login()
    cookies = str(client.cookies)
    assert "portal_session" in cookies
    assert client.get("/api/v1/auth/me").json()["user"]["name"] == "Dinesh Chugtai"
    body = {"title": "VPN issue"}
    assert (
        client.post("/api/v1/tickets", json=body, headers={"X-CSRF-Token": "wrong"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/tickets", json=body, headers={"Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    assert client.post("/api/v1/tickets", json={**body, "actor_id": str(uid(6))}).status_code == 422
    assert client.post("/api/v1/tickets", json=body).status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/tasks").status_code == 401
    with database() as db:
        assert not db.scalar(select(SessionToken))


def test_expired_session(client, login, database):
    login()
    with database.begin() as db:
        db.scalar(select(SessionToken)).expires_at = utcnow() - timedelta(seconds=1)
    assert client.get("/api/v1/auth/me").status_code == 401


def test_demo_gating(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)
    assert client.get("/api/v1/auth/demo-accounts").status_code == 404
    assert client.post("/api/v1/auth/demo-login", json={"user_id": str(uid(2))}).status_code == 404


def test_rest_timesheet_approval_and_audit(client, login):
    login(2)
    entry = client.post(
        "/api/v1/time-entries",
        json={
            "project_id": str(uid(101)),
            "work_date": "2026-09-30",
            "hours": 7,
            "description": "Integration work",
        },
    )
    assert entry.status_code == 200, entry.text
    response = client.post("/api/v1/timesheets/submit?week=2026-09-30")
    assert response.status_code == 200, response.text
    sid = response.json()["id"]
    login(1)
    assert client.get("/api/v1/approvals").json()["total"] == 1
    response = client.post(f"/api/v1/timesheets/{sid}/approve")
    assert response.status_code == 200 and response.json()["status"] == "APPROVED"
    assert client.get("/api/v1/audit-events?source=UI").json()["total"] == 3


def test_list_validation_and_identity_spoofing(client, login):
    login(2)
    assert client.get("/api/v1/tasks?limit=1000").status_code == 422
    assert client.get("/api/v1/tasks?status=anything").status_code == 422
    assert (
        client.post(
            "/api/v1/time-entries",
            json={
                "project_id": str(uid(101)),
                "work_date": "2026-09-30",
                "hours": 7,
                "description": "Work",
                "user_id": str(uid(3)),
            },
        ).status_code
        == 422
    )
    assert client.get("/api/v1/approvals").status_code == 403


@pytest.mark.parametrize("description", [None, "", "  "])
def test_logging_and_updating_without_description(client, login, description):
    login(2)
    body = {"project_id": str(uid(101)), "work_date": "2026-10-01", "hours": 7}
    if description is not None:
        body["description"] = description
    response = client.post("/api/v1/time-entries", json=body)
    assert response.status_code == 200, response.text
    entry = response.json()
    assert entry["description"] == ""
    response = client.put(f"/api/v1/time-entries/{entry['id']}", json={**body, "hours": 8})
    assert response.status_code == 200, response.text
    assert response.json()["description"] == ""
    assert client.post("/api/v1/timesheets/submit?week=2026-09-28").status_code == 200
