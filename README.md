# Pied Piper Operations

A Silicon Valley–themed Pied Piper enterprise portal for everyday work: timesheets, tasks, leave, support tickets, an employee directory, manager review, and activity logs.

This release implements the **enterprise web application only**. MCP integration is intentionally deferred. REST endpoints already call shared business services so a future MCP adapter can reuse the same permissions, validation, workflows, and transactions.

## Run locally

Install Docker Desktop, start it, then run from the repository root:

```sh
docker compose up --build -d
```

Open **http://localhost:3000**. API documentation is at **http://localhost:8000/docs**. The initialization container applies Alembic migrations and seeds demo records before starting the app.

| Account           | Role     | Team                                   |
| ----------------- | -------- | -------------------------------------- |
| Dinesh Chugtai    | Employee | Engineering; reports to Gilfoyle       |
| Jared Dunn        | Employee | Operations; reports to Gilfoyle        |
| Bertram Gilfoyle  | Manager  | Engineering                            |
| Erlich Bachman    | Employee | Business Operations; reports to Monica |
| Monica Hall       | Manager  | Business Operations                    |
| Richard Hendricks | Admin    | Leadership; all records                |

The reporting relationships are chosen for the permission demo rather than reproducing the show. The seven modules and workflow rules are unchanged.

Select a demo account at login. Use the switch-account button in the header to change identities.

Tabs in the same browser share a session. Switching accounts or signing out synchronizes the other tabs and closes their unsaved forms. Use separate browser profiles if you want employee and manager accounts signed in at the same time.

Stop with `docker compose down`. To **delete local demo data and reset everything**, run:

```sh
docker compose down --volumes
docker compose up --build -d
```

The reset command deletes this project's PostgreSQL volume. Normal startup and the seed command preserve existing workflows. Seeding refreshes demo names, emails, departments and project labels in place, so existing timesheets, requests, assignments, sessions and audit history stay attached to the same IDs. Edited sample tasks and tickets are preserved.

## Architecture

```mermaid
flowchart LR
  UI[Next.js web UI] --> REST[FastAPI REST API]
  REST --> Services[Shared business services]
  Future[Future MCP adapter] -. deferred .-> Services
  Services --> DB[(PostgreSQL)]
  Services --> Audit[Transactional audit records]
  Audit --> DB
```

- Frontend: Next.js App Router, TypeScript, Tailwind CSS, responsive seven-view portal.
- Backend: FastAPI, Pydantic, SQLAlchemy, Alembic.
- Database: PostgreSQL 16. SQLite is supported for isolated tests and quick local previews.
- Authentication: allowlisted demo accounts with opaque, hashed server sessions; eight-hour expiry; HttpOnly, SameSite cookies; CSRF token and Origin checks for writes.
- Business rules live in `backend/app/services`. Handlers only validate transport inputs and invoke services with an authenticated actor context. The backend reloads the actor's current role from the database.
- Successful changes and audits share one transaction. Permission denials and business validation failures roll back changes and produce separate DENIED/FAILED events. Unauthenticated requests and transport schema failures do not create business audit events.
- PostgreSQL actor locks serialize entry-total and leave-overlap checks. Resource locks ensure only one reviewer can decide a pending request.

## Workflows and permissions

**Timesheets:** a weekly project-by-day grid shows every assigned project, with seven MM/DD date columns and zero for empty days. Select any date to view its Monday–Sunday week. Descriptions are optional when logging or editing time. Click an empty cell to log time with its project/date prefilled, or a populated cell to inspect and manage individual entries; multiple entries are summed per cell. Zeroes are display defaults and create no database records. Monday-start weeks, active assigned projects, decimal hours greater than zero, at most 24 hours per day. Draft entries can be edited or deleted. Nonempty sheets can be submitted. Managers approve or reject direct-report sheets; rejection requires a reason. Editing a rejected sheet returns it to draft. Submitted and approved sheets are locked.

**Tasks:** managers create, edit and assign within their team; employees see and change the status of tasks assigned to them. States are TODO, IN_PROGRESS and DONE; reopening is allowed.

**Leave:** inclusive calendar dates, no overlap with pending or approved requests. Managers review direct reports. No balances, holidays or partial days.

**Tickets:** employees create and view their own tickets, and change their status. Managers and admins manage all tickets, including priority and assignment to active users. Transitions are OPEN → IN_PROGRESS → RESOLVED → CLOSED; resolved/closed tickets can reopen to OPEN, and in-progress tickets can return to OPEN.

**Directory:** authenticated users can search seeded employee records by name, email, department or manager name, and filter by department/manager ID.

**Manager review:** one pending queue for timesheets and leave. Own requests are excluded. Admins can review all other users' requests. Self-approval and self-rejection are forbidden for every role.

**Activity:** employees see their own actions; managers see their own and direct-report actions; admins see all. Filter by actor, source, action, resource, outcome and dates. All current actions have source UI; the source field supports future MCP integration without implementing a server.

Dates use America/Chicago; timestamps are stored in UTC. Workflow views refresh every ten seconds while visible, after mutations, and on window focus.

## Development without containerized app services

Python 3.13 and Node.js 20.9+ are supported; Docker builds use Node.js 22.

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cp .env.example .env
docker compose up -d db
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/python -m backend.app.demo seed
.venv/bin/uvicorn backend.app.main:app --reload --port 8000
```

In a second terminal:

```sh
npm ci --prefix frontend
npm run dev --prefix frontend
```

If PostgreSQL is unavailable, set `DATABASE_URL=sqlite:////tmp/orbit-local.db` in `.env` and apply the same migrations and seed commands. SQLite does not provide the PostgreSQL concurrency guarantees; use PostgreSQL for the full demo.

Demo mode defaults to disabled in application settings and is explicitly enabled in Compose and `.env.example`. This app has no production identity provider yet. Do not expose demo login on a public deployment. The UI uses same-origin API proxying; `WEB_ORIGIN` must match the browser origin. Set `SECURE_COOKIES=true` when using HTTPS.

## REST API

All application endpoints use `/api/v1`; lists return `{items, total, limit, offset}` and support pagination. Full typed schemas and endpoint details are generated in `/docs`.

- `/auth/demo-accounts`, `/auth/demo-login`, `/auth/me`, `/auth/logout`
- `/employees`, `/employees/{id}`, `/projects`, `/projects/{id}`
- `/timesheets/me?week=YYYY-MM-DD`, `/timesheets/{id}`, `/timesheets/submit?week=...`
- `/time-entries`: POST; `/time-entries/{id}`: PUT/DELETE
- `/timesheets/{id}/approve` and `/reject`: POST
- `/tasks`: GET/POST; `/tasks/{id}`: GET/PUT; `/assignee` and `/status`: PATCH
- `/leave-requests`: GET/POST; `/leave-requests/{id}`: GET; `/approve` and `/reject`: POST
- `/tickets`: GET/POST; `/tickets/{id}`: GET; `/assignee`, `/priority`, `/status`: PATCH
- `/approvals`, `/audit-events`

Identity and source are never accepted as mutation body fields. Authenticated writes require `X-CSRF-Token` from login or `/auth/me`, together with the configured `Origin` header. Sessions are cookies, not bearer credentials.

## Verification

```sh
.venv/bin/pytest -q
npm run typecheck --prefix frontend
npm run build --prefix frontend
```

For PostgreSQL locking tests, create a **disposable test database**:

```sh
docker compose exec db createdb -U portal portal_test
TEST_DATABASE_URL=postgresql+psycopg://portal:portal@localhost:5433/portal_test .venv/bin/pytest -q
```

These tests recreate tables in the test database. They refuse URLs without `test` in the database name. Never point them at your development or production database.

Browser checks start isolated API/UI servers and a temporary SQLite database:

```sh
cd frontend
npx playwright install chromium
npm run test:e2e
```

Tests cover the employee-to-manager timesheet lifecycle, task assignment/completion, leave overlap/rejection, ticket triage, directory searches, mobile navigation and automatic UI refresh after an external API write.

## Demo walkthrough

1. Sign in as Dinesh, log seven hours on Compression Engine and describe the work.
2. Edit the draft entry, then submit the week. The sheet becomes locked.
3. Switch to Gilfoyle, open Manager Review, inspect entries, and approve.
4. Switch back to Dinesh to see APPROVED and the reviewer name.
5. Create leave, then review it as Gilfoyle; try an overlapping request to see validation.
6. As Gilfoyle, assign a task to Jared. As Jared, mark it DONE.
7. Create a support ticket as an employee; assign and resolve it as a manager.
8. Search the directory for Dinesh and inspect his manager. Open Activity to see actions and outcomes.

## Deferred

MCP server/tools and agent clients, cloud deployment, employee/project administration, notifications, file uploads, payroll, leave accrual, expenses, equipment requests, and multitenancy.
