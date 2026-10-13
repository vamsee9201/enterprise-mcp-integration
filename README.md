# Natural-language access to SaaS with MCP and Codex

People use SaaS platforms to get work done: log time, request leave, assign tasks, resolve support issues, and review approvals. Each action usually means finding the right application, navigating its menus, filling out a form, and checking the result. When a workflow spans several screens or platforms, navigation becomes part of the job.

A natural-language interface lets people describe the outcome they want: **“Log seven hours on Compression Engine for Monday and submit my timesheet.”** An agent can find the project, identify the correct week, and perform the relevant operations. This can reduce repetitive navigation and make capabilities easier to discover, especially for people who use a platform only occasionally.

This repository demonstrates that idea with a Silicon Valley–themed SaaS application, an authenticated Model Context Protocol (MCP) server, and Codex as the conversational interface. The web application makes the underlying records and workflow results visible; Codex lets users work with those same records through natural language.

## What is an MCP server?

The **Model Context Protocol (MCP)** defines a standard way for AI applications to discover and call tools, and to access resources and prompts supplied by external systems. An MCP server exposes a system's capabilities through that protocol. The AI application connects as a client, discovers the available capabilities, and uses them to respond to a user's request.

For a SaaS platform, tools can represent business operations such as finding an employee, logging time, submitting a timesheet, or approving leave. Each tool has a name, description, and structured input/output contract. The agent translates the user's request into tool calls; the server authenticates those calls and the application enforces its permissions and business rules.

In this project, the MCP server exposes **33 typed tools** over **Streamable HTTP** using FastMCP. Codex connects to it with a persona-specific bearer credential. The server supplies application capabilities; Codex supplies the language model and conversational experience. Starting the portal and MCP server does not require a model API key.

See the [MCP introduction](https://modelcontextprotocol.io/docs/getting-started/intro) and [official Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp?surface=cli) for protocol and client background.

## First, build a SaaS platform

To demonstrate an agent operating a SaaS platform, we first needed a platform with real records, users, and workflows. **Pied Piper Operations** is a fictional internal enterprise portal inspired by *Silicon Valley*. Its employees include Dinesh, Gilfoyle, Jared, Monica, Erlich, and Richard.

The application provides seven modules: timesheets, tasks, leave, support tickets, an employee directory, manager review, and activity logs. It includes employee, manager, and administrator roles, persistent data, validation, approvals, and auditing. The reporting relationships are chosen to demonstrate permissions rather than reproduce the show.

The next layer is the MCP integration. The web API and MCP tools call the **same business services**, so completing a task through Codex changes the same record shown in the portal. The agent gets the authenticated user's permissions, and writes produce activity events identifying MCP as their source.

Finally, Codex connects to the MCP server. A user can discover their projects, submit work, or handle a support issue in conversation, then inspect the result in the web application. This is an example of adding an agent interface to an existing product without duplicating its workflow logic.

## Architecture

| Component | Technology / location | Responsibility |
| --- | --- | --- |
| Web portal | Next.js 15, React 19, TypeScript, Tailwind CSS; `frontend/` | Seven application views, forms, account switching, and visible workflow results. Proxies `/api` requests to the backend. |
| REST API | FastAPI and Pydantic; `backend/app/api/` | Browser authentication, typed request validation, and application endpoints under `/api/v1`. |
| MCP server | FastMCP 2.14.7 and MCP SDK 1.25.0; `mcp_server/` | Exposes 33 typed tools at `/mcp`, authenticates bearer credentials, and applies scope and request limits. |
| Shared business services | `backend/app/services/portal.py` | Enforces ownership, team access, workflow transitions, validation, and auditing for both REST and MCP. |
| Persistence | Google Cloud Firestore; `backend/app/database/` and `backend/app/models/` | Stores application records, sessions, credentials, retry records, and audit events. Local development uses the Firestore emulator. |
| Authentication | `backend/app/auth/` | Separate web sessions and MCP credentials, stored as token hashes; resolves the user's current role and access. |
| Agent client | Codex | Interprets natural language, discovers tools, resolves record names, and invokes permitted operations. |
| Optional chat application | Google ADK and Vertex AI; `chat_app/` | An additional conversational client that performs business operations through MCP. Requires separate cloud/model setup. |
| Verification | pytest, Ruff, TypeScript, Playwright | Service, API, MCP, concurrency, and browser checks; some harnesses still require migration updates described below. |

**Web request path:** browser → REST API → shared services → Firestore.

**Agent request path:** user → Codex → MCP server → shared services → Firestore.

Successful business changes and their audit records commit together. Creation tools support retry keys to prevent duplicate records after an uncertain response. Each tool call commits separately: if logging time succeeds but submission fails, the entry remains saved.

## Run on your own machine

### Current repository state

The backend, MCP server, and ADK chat use Firestore. Local and CI tests use isolated emulator namespaces; deployment uses a dedicated Firestore database. Docker Compose starts the emulator and seeds the app. See [Firestore deployment and recovery](docs/FIRESTORE.md).

### Prerequisites

- Git, Python **3.13**, and Node.js **22** with npm.
- Google Cloud CLI with the Firestore emulator component and Java **25 or later**. See [Google's emulator setup](https://docs.cloud.google.com/firestore/native/docs/emulator).
- Codex installed and signed in if you want to use the natural-language interface. The portal can run independently.
- Available local ports: **8787** (emulator), **8000** (REST), **8001** (MCP), and **3000** (web).

Commands below use a POSIX shell such as bash or zsh. On Windows, use WSL or adapt the virtual-environment paths and environment-variable syntax.

### 1. Clone and install

```sh
git clone https://github.com/vamsee9201/enterprise-mcp-integration.git
cd enterprise-mcp-integration
python3.13 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
npm ci --prefix frontend
```

### 2. Start the Firestore emulator

In a dedicated terminal, start the emulator and leave it running:

```sh
gcloud emulators firestore start --host-port=127.0.0.1:8787
```

If the component is missing, install it using your Google Cloud CLI installation's supported component/package mechanism. The local emulator does not require access to the project's deployed cloud resources.

### 3. Configure, seed, and start the API

From the repository root, create a local `.env` with these settings. If you already have one, update the relevant values instead of overwriting unrelated settings:

```dotenv
FIRESTORE_PROJECT=demo-enterprise-portal
FIRESTORE_DATABASE=(default)
FIRESTORE_NAMESPACE=portal
DEMO_MODE=true
WEB_ORIGIN=http://localhost:3000
APP_TIMEZONE=America/Chicago
SECURE_COOKIES=false
MCP_AUTH_MODE=demo
MCP_PUBLIC_URL=http://localhost:8001/mcp
```

Export the emulator address in **every terminal running a Python application, token command, or test**. It is read by the Firestore SDK from the process environment:

```sh
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8787
.venv/bin/python -m backend.app.demo seed
.venv/bin/uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Seeding creates the demo users, projects, and sample records. Repeated seeding preserves existing workflow records and refreshes reference data in place.

### 4. Start the MCP server

In another terminal at the repository root:

```sh
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8787
.venv/bin/uvicorn mcp_server.asgi:app --host 127.0.0.1 --port 8001
```

### 5. Start the frontend

In another terminal at the repository root:

```sh
npm run dev --prefix frontend
```

| Service | Local address |
| --- | --- |
| Web portal | [http://localhost:3000](http://localhost:3000) |
| REST API documentation | [http://localhost:8000/docs](http://localhost:8000/docs) |
| REST health check | [http://localhost:8000/health](http://localhost:8000/health) |
| MCP readiness | [http://localhost:8001/ready](http://localhost:8001/ready) |
| MCP endpoint | `http://localhost:8001/mcp` — connect with an authenticated MCP client |

Select a demo account in the portal. Stop each process with **Ctrl+C**. The default emulator is in memory, so stopping it discards local data; restart it and seed again for a fresh demo. For persistence between runs, consult the emulator's import/export options.

### Demo accounts

| Account | Role | Team / reporting relationship |
| --- | --- | --- |
| Dinesh Chugtai | Employee | Engineering; reports to Gilfoyle |
| Jared Dunn | Employee | Operations; reports to Gilfoyle |
| Bertram Gilfoyle | Manager | Engineering |
| Erlich Bachman | Employee | Business Operations; reports to Monica |
| Monica Hall | Manager | Business Operations |
| Richard Hendricks | Admin | Leadership; access across the organization |

Browser tabs share a session. Switching accounts or signing out synchronizes other tabs and closes their unsaved forms. Use separate browser profiles for simultaneous employee and manager sessions.

## Connect the MCP server to Codex

### Issue a persona credential

In a terminal at the repository root, with the emulator running:

```sh
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8787

# Dinesh: employee, with default read/write scopes
.venv/bin/python -m backend.app.demo issue-mcp-token \
  --user-id 00000000-0000-4000-8000-000000000002

# Gilfoyle: manager, including permission to call review tools
.venv/bin/python -m backend.app.demo issue-mcp-token \
  --user-id 00000000-0000-4000-8000-000000000001 \
  --scope portal:read --scope portal:write --scope portal:review
```

Each command prints a raw token once and a separate credential ID. Keep the token private and retain the ID for revocation. Tokens expire after eight hours by default; `--hours` supports up to 24. A read-only credential uses `--scope portal:read`. Review scope does not override team restrictions or the ban on self-review.

For the admin walkthrough, issue a token with the same three scopes for Richard: `00000000-0000-4000-8000-000000000006`.

### Configure the connection

Add this secret-free configuration to your personal `~/.codex/config.toml`:

```toml
[mcp_servers.pied_piper]
url = "http://localhost:8001/mcp"
bearer_token_env_var = "PIED_PIPER_MCP_TOKEN"
startup_timeout_sec = 20
tool_timeout_sec = 30
```

Supply the token to the Codex process through its environment. For a terminal demonstration with **zsh**, use a hidden prompt and launch Codex from that shell:

```sh
read -s 'PIED_PIPER_MCP_TOKEN?Paste your MCP token: '
export PIED_PIPER_MCP_TOKEN
codex
```

Use `codex mcp list` to inspect configured servers and `/mcp` inside the Codex terminal interface to inspect active connections. See [official Codex MCP configuration guidance](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

A shell export does not update an already-running desktop application's environment. For desktop use, supply the credential through the app's supported MCP setup or launch it with the configured environment.

Start with: **“Use Pied Piper get_my_context and tell me who I am.”** Verify the identity before making changes. Switching the portal account does not switch the MCP credential. For the simplest demo, use one active persona connection at a time and reconnect in a fresh session after changing the token.

To revoke a credential:

```sh
.venv/bin/python -m backend.app.demo revoke-mcp-token \
  --credential-id YOUR_CREDENTIAL_UUID
```

## Demonstrate the natural-language workflow

Keep the portal open beside Codex. Visible views refresh every ten seconds, after web mutations, and on window focus. Choose an unused timesheet week and leave dates when repeating the demonstration.

| Persona | Example request | Expected result |
| --- | --- | --- |
| Dinesh | “Who is my manager, and which projects can I log time to?” | Codex discovers the user's manager and assigned projects through MCP. |
| Dinesh | “Log seven hours on Compression Engine for May 3, 2027, without a description, then submit that week's timesheet.” | A time entry is saved and the week becomes SUBMITTED. |
| Gilfoyle | “Show pending approvals and approve Dinesh's May 3, 2027 timesheet.” | The sheet becomes APPROVED and leaves the pending queue. |
| Gilfoyle | “Create a task for Dinesh called Investigate compression performance.” | A task is created and assigned to Dinesh. |
| Dinesh | “Mark Investigate compression performance as done.” | The assigned task becomes DONE. |
| Dinesh | “Request leave for May 17–19, 2027.” | A PENDING leave request is created. |
| Gilfoyle | “Reject Dinesh's May 17–19 leave because team coverage is required.” | The request becomes REJECTED with feedback. |
| Dinesh | “Create a high-priority ticket called Demo VPN issue.” | A support ticket is created. |
| Gilfoyle | “Assign Demo VPN issue to Dinesh.” | The ticket's assignee changes. |
| Dinesh | “The VPN issue is fixed. Close Demo VPN issue.” | The ticket becomes CLOSED. |
| Gilfoyle | “Request leave for June 28–29, 2027, then approve my own request.” | Creation succeeds; self-approval is denied. |
| Richard | “Approve Gilfoyle's June 28–29 leave, then show recent MCP activity.” | The leave is approved; activity includes successful and denied actions. |

These requests create real demo records. An ambiguous name should lead to clarification. A submitted or approved timesheet cannot be edited, and a permission denial should remain a denial regardless of how the request is phrased.

The [three-persona demo guide](docs/MCP_DEMO.md) includes presentation prompts. The [MCP reference](docs/MCP.md) contains detailed tool contracts and retry behavior; it includes Firestore setup and current runtime contracts.

## Workflows and permissions

| Module | Behavior and rules |
| --- | --- |
| Timesheets | Monday–Sunday project/day grid; assigned active projects; positive decimal hours with at most two decimal places and a 24-hour daily total limit. Descriptions are optional. Draft entries can be edited/deleted; nonempty sheets can be submitted. Submitted/approved sheets are locked. Rejection requires feedback; editing a rejected sheet returns it to draft. |
| Tasks | Managers create, edit, and assign within their permitted team; employees see assigned tasks and change their status. States: TODO, IN_PROGRESS, DONE; reopening is allowed. |
| Leave | Inclusive calendar dates; pending/approved requests cannot overlap. Managers review direct reports. No leave balances, holiday calculations, or partial days. |
| Support tickets | Employees access tickets they created or currently hold as assignee. Managers/admins see all tickets and control assignment and existing-ticket priority. Authorized users can select OPEN, IN_PROGRESS, RESOLVED, or CLOSED, including direct closure and reopening. Reassignment removes the former assignee's access unless they are also the creator. |
| Directory | Authenticated search by name, email, department, or manager name; department/manager filters. |
| Manager review | Combined pending timesheet/leave queue. Managers review direct reports; admins can review other users. Nobody can approve or reject their own requests. |
| Activity | Employees see their own actions; managers see their own and direct-report actions; admins see all. Filters include actor, source, action, resource, outcome, and dates. UI and MCP writes are distinguishable. |

Dates use **America/Chicago**; timestamps are stored in UTC. Empty timesheet cells display zero without creating zero-hour records, and multiple entries in a cell are summed.

## MCP tool coverage

| Area | Tools |
| --- | --- |
| Identity | `get_my_context` |
| Directory and projects | `search_employees`, `get_employee`, `list_projects`, `get_project` |
| Timesheets | `list_timesheets`, `get_my_timesheet`, `get_timesheet`, `add_time_entry`, `update_time_entry`, `delete_time_entry`, `submit_timesheet`, `approve_timesheet`, `reject_timesheet` |
| Tasks | `list_tasks`, `get_task`, `create_task`, `update_task`, `assign_task`, `update_task_status` |
| Leave | `list_leave_requests`, `get_leave_request`, `request_leave`, `approve_leave`, `reject_leave` |
| Tickets | `list_tickets`, `get_ticket`, `create_ticket`, `assign_ticket`, `update_ticket_priority`, `update_ticket_status` |
| Review and activity | `list_pending_approvals`, `get_recent_activity` |

Tool IDs are UUIDs obtained from search/list results. Dates use ISO format. Lists default to 50 records and allow up to 100 per page. Mutation responses include `record`, `request_id`, and `replayed`; list responses include pagination fields and a request ID.

The four creation tools—`add_time_entry`, `create_task`, `request_leave`, and `create_ticket`—require an `idempotency_key` UUID. Use a new key for a new action and reuse it only when retrying the same action with identical arguments after an uncertain result. A replay returns the original creation result without duplicating the write or success audit event. Reusing a key with changed arguments conflicts. Other mutations have their own workflow semantics; repeated approvals conflict.

## REST API and authentication

Application endpoints are under `/api/v1`. The running [API documentation](http://localhost:8000/docs) provides typed schemas and exact parameters.

| Area | Endpoint families |
| --- | --- |
| Authentication/context | `/auth/demo-accounts`, `/auth/demo-login`, `/auth/me`, `/auth/logout`, `/context` |
| Directory/projects | `/employees`, `/employees/{id}`, `/projects`, `/projects/{id}` |
| Timesheets | `/timesheets`, `/timesheets/me`, `/timesheets/{id}`, `/timesheets/submit`, `/time-entries`; approval/rejection routes |
| Tasks | `/tasks`, `/tasks/{id}`; detail, assignee, and status updates |
| Leave/tickets | `/leave-requests`, `/tickets`; detail and workflow routes |
| Review/activity | `/approvals`, `/audit-events` |

Web authentication uses eight-hour opaque sessions in HttpOnly, SameSite cookies. Authenticated browser writes require the CSRF token returned by login or `/auth/me` and an allowed `Origin`. MCP uses separate bearer credentials with read/write/review scopes. Identity and action source come from authentication, never mutation-body fields.

MCP checks allowed hosts/origins and defaults to 120 authenticated HTTP requests per minute per credential. Missing, expired, or revoked credentials return 401; rate limits return 429 with `Retry-After`. Business failures return tool errors with safe categories and correlation IDs. Record descriptions and other user-entered text are data, and must not be treated as agent instructions.

## Development and verification

The repository includes tests for permissions, workflow validation, authentication, REST/MCP parity, retries, auditing, concurrency, and browser interactions. With the Firestore emulator running, execute the full verification gate:

```sh
export FIRESTORE_EMULATOR_HOST=127.0.0.1:8787
python3.13 -m venv .venv-chat
.venv-chat/bin/pip install -r chat_app/requirements.txt pytest==9.0.2
make verify
```

Backend fixtures create isolated `test-` namespaces and delete them afterward. Use the local emulator for these checks. The commands above are verification instructions, not a claim that the current working tree passes every test.

`make check`, `make verify`, GitHub CI and browser fixtures now use Firestore. CI starts the emulator automatically. Browser tests use isolated ports 3020/8020 and an automatically allocated MCP port. Real Firestore tests are opt-in with `FIRESTORE_LIVE_TESTS=1` and clean only generated `test-` namespaces.

For MCP inspection, run `npx @modelcontextprotocol/inspector`, choose Streamable HTTP, and enter `http://localhost:8001/mcp` with the persona bearer token in its authentication settings. The default allowed Inspector origin is `http://localhost:6274`.

| Directory / file | Contents |
| --- | --- |
| `frontend/` | Portal UI, API client, and browser tests |
| `backend/app/` | REST routes, authentication, business services, models, and Firestore persistence |
| `backend/tests/` | Service, API, MCP, seed, and concurrency tests |
| `mcp_server/` | Server, tool definitions, adapter, and response contracts |
| `chat_app/` | Optional ADK chat client, UI, and tests |
| `scripts/mcp_demo.py` | Real HTTP MCP demonstration; creates actual workflow records |
| `docs/` | MCP/demo guides, historical deployment/chat instructions, and verification evidence |
| `deploy/` | Firestore Cloud Run deployment and one-time protected SQL export/import utilities |
| `compose.yaml` | Local Firestore emulator and application startup |

## Optional chat and deployment

The [ADK chat guide](docs/CHAT.md) describes an additional MCP client using Vertex AI. It requires its own cloud credentials, model access, and service configuration. The [deployment guide](docs/DEPLOYMENT.md) describes the current private Cloud Run services, and the [Firestore test report](docs/FIRESTORE_TEST_REPORT.md) records migration, automated verification and deployed browser/agent results.

This remains a demo with selectable personas and locally issued MCP credentials. Production adoption requires real user authentication, OAuth identity mapping for MCP, HTTPS, managed secrets, deployment configuration, and production operational controls. Demo login must stay behind an appropriate access boundary.

Future extensions include notifications, employee/project administration, attachments, leave accrual, payroll, expenses, equipment requests, and multitenancy. They are possible applications of the approach, not implemented capabilities.

## Conclusion

A SaaS platform's value comes from the work it enables. Natural language can make that work easier to access: employees can record time or request leave without remembering navigation paths, managers can discover pending reviews and delegate tasks in one conversation, and support staff can find and update issues while discussing them.

For companies, exposing well-defined business operations through MCP can reduce the need to build a complex frontend for every internal workflow or role. A shared agent interface can handle many routine interactions while engineering effort goes into reliable services, permissions, and data quality. Visual interfaces still help with grids, dashboards, bulk review, and checking results; this project's portal shows how both interfaces can coexist.

The same approach could support CRM updates, onboarding checklists, procurement requests, incident coordination, and cross-platform workflows through multiple authorized MCP integrations. It could also make infrequent tasks easier to discover and enable conversational or voice-based access. Those opportunities depend on clear tool contracts and dependable application behavior.

Pied Piper Operations demonstrates the central idea: **describe the work in natural language, let the agent call the right tools, and let the SaaS platform enforce the rules and record the result.**
