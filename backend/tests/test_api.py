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


def test_rest_assigned_ticket_permissions_and_audit(client, login):
    login(4)
    created = client.post("/api/v1/tickets", json={"title": "REST assignment contract"}).json()
    tid = created["id"]
    assert (
        client.patch(
            f"/api/v1/tickets/{tid}/assignee", json={"assignee_id": str(uid(2))}
        ).status_code
        == 200
    )
    login(2)
    listed = client.get("/api/v1/tickets?query=REST%20assignment").json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == tid
    assert client.get(f"/api/v1/tickets/{tid}").status_code == 200
    assert (
        client.patch(f"/api/v1/tickets/{tid}/status", json={"status": "IN_PROGRESS"}).status_code
        == 200
    )
    assert (
        client.patch(f"/api/v1/tickets/{tid}/priority", json={"priority": "LOW"}).status_code == 403
    )
    assert (
        client.patch(
            f"/api/v1/tickets/{tid}/assignee", json={"assignee_id": str(uid(3))}
        ).status_code
        == 403
    )
    events = client.get("/api/v1/audit-events?resource_type=ticket").json()["items"]
    assert all(event["source"] == "UI" and event["request_id"] for event in events)
    assert sum(event["outcome"] == "DENIED" for event in events) == 2
    login(3)
    assert client.get(f"/api/v1/tickets/{tid}").status_code == 403
    assert client.get("/api/v1/tickets?query=REST%20assignment").json()["total"] == 0


def test_rest_task_edit_assignment_status_and_filters(client, login):
    login(1)
    response = client.post("/api/v1/tasks", json={"title": "REST task", "assignee_id": str(uid(2))})
    assert response.status_code == 200
    tid = response.json()["id"]
    assert (
        client.put(
            f"/api/v1/tasks/{tid}",
            json={
                "title": "REST edited task",
                "project_id": str(uid(102)),
                "due_date": "2027-05-01",
            },
        ).status_code
        == 200
    )
    assert (
        client.patch(f"/api/v1/tasks/{tid}/assignee", json={"assignee_id": str(uid(3))}).status_code
        == 200
    )
    login(2)
    assert client.get(f"/api/v1/tasks/{tid}").status_code == 403
    login(3)
    assert (
        client.patch(f"/api/v1/tasks/{tid}/status", json={"status": "DONE"}).json()["status"]
        == "DONE"
    )
    assert client.get("/api/v1/tasks?query=REST&status=DONE").json()["total"] == 1
    assert (
        client.put(f"/api/v1/tasks/{tid}", json={"title": "Unauthorized edit"}).status_code == 403
    )


@pytest.mark.parametrize(
    "path,body",
    [
        ("/tickets", {"title": "Spoofed", "source": "MCP"}),
        (
            "/leave-requests",
            {"start_date": "2027-05-01", "end_date": "2027-05-02", "user_id": str(uid(3))},
        ),
        ("/tasks", {"title": "Spoofed", "assignee_id": str(uid(2)), "creator_id": str(uid(3))}),
    ],
)
def test_rest_mutations_reject_identity_and_source_fields(client, login, path, body):
    login(1)
    assert client.post(f"/api/v1{path}", json=body).status_code == 422


def test_rest_leave_review_and_filtered_directory_projects(client, login):
    login(2)
    assert client.get(f"/api/v1/employees/{uid(2)}").json()["manager_name"] == "Bertram Gilfoyle"
    assert client.get("/api/v1/projects?query=PiperNet").json()["total"] == 1
    response = client.post(
        "/api/v1/leave-requests", json={"start_date": "2027-05-01", "end_date": "2027-05-01"}
    )
    assert response.status_code == 200
    lid = response.json()["id"]
    login(4)
    assert client.get(f"/api/v1/leave-requests/{lid}").status_code == 403
    assert client.post(f"/api/v1/leave-requests/{lid}/approve").status_code == 403
    login(1)
    assert client.get("/api/v1/approvals?kind=leave").json()["total"] == 1
    assert (
        client.post(f"/api/v1/leave-requests/{lid}/reject", json={"reason": " "}).status_code == 422
    )
    assert client.post(f"/api/v1/leave-requests/{lid}/approve").json()["status"] == "APPROVED"
    assert client.post(f"/api/v1/leave-requests/{lid}/approve").status_code == 409
    login(2)
    assert client.get("/api/v1/leave-requests?status=APPROVED").json()["total"] == 1


def test_session_rotation_stores_hash_and_reloads_account_permissions(client, login, database):
    from backend.app.auth.tokens import digest
    from backend.app.models.entities import User

    login(1)
    previous = client.cookies.get("portal_session")
    with database() as db:
        session = db.scalar(select(SessionToken))
        assert session.token_hash == digest(previous) and session.token_hash != previous
    login(4)
    with database() as db:
        assert (
            db.scalar(select(SessionToken).where(SessionToken.token_hash == digest(previous)))
            is None
        )
    # Permissions come from current database state, not the role at sign-in.
    with database.begin() as db:
        db.get(User, uid(4)).role = "EMPLOYEE"
    assert (
        client.post(
            "/api/v1/tasks", json={"title": "Stale manager privilege", "assignee_id": str(uid(4))}
        ).status_code
        == 403
    )
    with database.begin() as db:
        db.get(User, uid(4)).active = False
    assert client.get("/api/v1/auth/me").status_code == 401


def test_browser_fixture_reset_is_not_an_application_endpoint(client):
    assert client.post("/api/v1/__test/reset").status_code == 404
