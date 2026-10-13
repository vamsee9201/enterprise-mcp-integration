# Firestore persistence and deployment

The portal, MCP server and ADK chat use the official Python Firestore SDK. REST and MCP still share business services; authentication and authorization remain server-side. Cloud Run uses workload identities rather than service-account keys in containers.

## Local setup

Install Python 3.13, Node 22, Google Cloud CLI with the Firestore emulator component, and Java 25. Start `gcloud emulators firestore start --host-port=127.0.0.1:8787` in a separate terminal. Copy `.env.example` to `.env`, install `backend/requirements-dev.txt` into `.venv`, install `chat_app/requirements.txt` and `pytest==9.0.2` into `.venv-chat`, then install frontend dependencies with `npm ci --prefix frontend`.

Set `FIRESTORE_EMULATOR_HOST=127.0.0.1:8787` in each terminal. Run `DEMO_MODE=true .venv/bin/python -m backend.app.demo seed`. Run the existing backend/MCP commands and `npm run dev --prefix frontend`; no SQL migration is needed. `make verify` runs backend/MCP, chat, TypeScript and production-browser checks. CI starts its own emulator. Browser harnesses use ports 3020/8020 and an allocated MCP port.

Docker Compose starts the official emulator image and the portal services. Emulator data is local test/demo data; use a protected export for anything that must survive abrupt container termination. The Compose runner explicitly exports a snapshot before graceful shutdown and imports the generated metadata on startup; restart preservation has been verified. Never treat it as a production database.

## Cloud layout

Project: `ai-lab-502500`. Dedicated database: `enterprise-portal`, Standard edition, Native mode, `us-central1`. Namespace: `enterprise_workspaces/portal`. This named database does **not** qualify for the default database's free quota. Reads, writes, deletes, storage and network transfer are billed by usage; there is no always-running database instance charge. PITR and scheduled backups are disabled. Existing `(default)` data and security rules are not changed.

The portal/MCP and chat runtime identities have conditional `roles/datastore.user` access scoped to `projects/ai-lab-502500/databases/enterprise-portal`. Services remain IAM-private, min instances zero and max instances two. The backend reads Firestore through Application Default Credentials. Browsers do not access Firestore directly.

Environment: `FIRESTORE_PROJECT`, `FIRESTORE_DATABASE`, `FIRESTORE_NAMESPACE`. `FIRESTORE_EMULATOR_HOST` must be absent in cloud revisions. `deploy/render_cloudrun.py` and `deploy/render_chat.py` render Firestore configuration without database credentials or Cloud SQL sockets. `deploy/issue_cloud_tokens.py` issues credentials using Firestore credentials; raw tokens are written only into a 0600 ignored file.

## Data and transactions

Collections mirror business entities. UUIDs are preserved. Dates are ISO calendar strings, timestamps UTC and hours integer hundredths. Credentials are stored as hashes. Chat messages, ADK events and turn results use separate subcollections.

Each business operation runs in a retryable Firestore transaction. Writes are buffered until all reads finish. Actor guard documents serialize absence checks (initial sheet creation and overlapping leave). Review reads conflict on the request document. Employee/week uniqueness and actor/operation/idempotency documents use deterministic keys. The resulting business record, retry result and success audit commit together. Failed/denied audit events commit separately.

The small document-query layer has no SQLAlchemy dependency. It uses indexed equality/membership queries to narrow candidates, then evaluates remaining filters, substring matches, stable ordering and exact totals in Python. This preserves existing interface contracts and targets the small portfolio dataset. Large activity histories or large teams would require query-specific indexes and cursor/count redesign. Page size alone does not bound candidate reads. Visible UI views refresh every ten seconds; hidden tabs stop polling.

`firestore.indexes.json` records index exemptions for large payload fields. No composite indexes are required by the current query strategy. Apply exemptions only to this dedicated database; do not overwrite another application's rules or indexes.

## Verification and recovery

Emulator tests create unique `test-` namespaces and clean them after execution. Live tests require `FIRESTORE_LIVE_TESTS=1`, cloud credentials and explicit database/project variables. Never use live test credentials against unrelated databases. Reset refuses production namespaces when the emulator is absent.

`deploy/firestore_migrate.py` exports all SQL entities under a repeatable-read snapshot into a protected JSON file, validates its SHA-256 checksum and references, imports records idempotently, and verifies exact normalized records. SQL dependencies are isolated in `deploy/requirements-migration.txt`; they are not runtime dependencies.

Before cutover, freeze source SQL writes, drain active chat turns, export/import/verify, then switch all services to Firestore. Keep the protected final export for recovery. Recovery imports into a new namespace and verifies it before updating service configuration. After new writes occur, the original SQL snapshot is no longer a complete rollback target.

Test evidence and retirement status are recorded in `FIRESTORE_TEST_REPORT.md`.
