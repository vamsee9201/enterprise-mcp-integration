"""Non-destructive health/login/read smoke check against the running Docker stack."""

import httpx

with httpx.Client(
    base_url="http://localhost:3000", headers={"Origin": "http://localhost:3000"}
) as client:
    accounts = client.get("/api/v1/auth/demo-accounts")
    accounts.raise_for_status()
    user = next(user for user in accounts.json() if user["name"] == "Dinesh Chugtai")
    response = client.post("/api/v1/auth/demo-login", json={"user_id": user["id"]})
    response.raise_for_status()
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    for path in (
        "/employees",
        "/projects",
        "/tasks",
        "/leave-requests",
        "/tickets",
        "/audit-events",
    ):
        response = client.get("/api/v1" + path)
        response.raise_for_status()
        print(f"{path}: OK ({response.json()['total']} records)")
    client.post("/api/v1/auth/logout").raise_for_status()
print("Docker stack smoke check passed.")
