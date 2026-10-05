# AI Lab cloud demo

Deployed and verified on October 5, 2026 in Google Cloud project **ai-lab-502500**, region **us-central1**.

| Component | Service / address |
| --- | --- |
| Portal (Next.js + FastAPI) | https://enterprise-portal-q7la2lmmlq-uc.a.run.app |
| MCP (33 tools, Streamable HTTP) | https://enterprise-mcp-q7la2lmmlq-uc.a.run.app/mcp |
| PostgreSQL 16 | Cloud SQL instance `enterprise-portal-db`, database `portal` |
| Migrations and clean seed | Cloud Run job `enterprise-portal-init` |
| Runtime identity | `enterprise-portal-runtime@ai-lab-502500.iam.gserviceaccount.com` |

Both services are **private and protected by Cloud Run IAM**. A direct unauthenticated browser request returns 403. This is an internal cloud demo with the existing allowlisted persona login; OAuth and production user authentication remain future work.

The two services share Cloud SQL and the existing business services, permissions, transactions, and audit events. The portal uses a frontend ingress container and a backend sidecar communicating over loopback. MCP runs separately. Both use the Cloud SQL connector socket and a Secret Manager reference for the database URL. No service-account key is installed in a container.

## Open the cloud portal

The service-account file was copied from `../lean-rag/ai-lab-fasa.json` into `ai-lab-fasa.json` at this repository's root. It is private (0600) and excluded from Git, Docker, and Cloud Build uploads. `.secrets/` and `.gcloud/` are excluded too.

Use an isolated CLI configuration so your normal Google Cloud login is unaffected:

```sh
export CLOUDSDK_CONFIG="$PWD/.gcloud"
gcloud auth activate-service-account --key-file=ai-lab-fasa.json --project=ai-lab-502500
gcloud run services proxy enterprise-portal \
  --project=ai-lab-502500 --region=us-central1 --port=3300
```

Leave that command running and open **http://localhost:3300**. This forwards to the deployed cloud app and cloud database. Local Docker at port 3000 still uses the local database.

Choose Dinesh (employee), Gilfoyle (manager), or Richard (admin). All six seeded personas and both projects are available. Switch accounts in the header. Separate browser profiles provide independent web sessions.

## Cloud MCP authentication

Cloud access requires **two independent credentials**:

1. A Google identity token for an identity with `roles/run.invoker`, sent in `X-Serverless-Authorization: Bearer <identity-token>`. Its audience is the canonical MCP service URL, without `/mcp`.
2. An application persona credential, sent in `Authorization: Bearer <persona-token>`.

Neither credential belongs in Git, chat messages, tool arguments, or command arguments. Google identity tokens expire and must be refreshed. The cloud persona credentials issued during deployment are valid for 24 hours; they are stored privately in `.secrets/cloud-personas.json`. Local credentials do not authenticate against the cloud database, and existing Codex persona connections still point to localhost.

The reusable cloud demonstration captures the Google token internally and reads the persona tokens from their private file:

```sh
# Choose an unused Monday-start week. This creates actual demo records.
.venv/bin/python deploy/cloud_demo.py --week 2026-10-12
```

This exercises Dinesh → Gilfoyle → Richard, including approvals, leave rejection, task completion, ticket assignment/closing/reopening, directory search, activity, authorization failures, and idempotent retry. You can watch the cloud portal update automatically.

For a Codex or other HTTP MCP client, configure the cloud MCP URL and both authentication headers using environment-backed secrets. A client or local gateway must refresh the Google identity token. The local persona configuration is intentionally preserved; no public unauthenticated MCP endpoint was created. Public deployment will require OAuth identity mapping and real web authentication.

### Renew cloud persona credentials

Use the same isolated `CLOUDSDK_CONFIG` in this terminal. Start a temporary Cloud SQL proxy; it exposes the database only on loopback:

```sh
docker run -d --name enterprise-cloud-sql-proxy \
  -p 127.0.0.1:5434:5432 \
  -v "$PWD/ai-lab-fasa.json:/credentials.json:ro" \
  gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.20.0 \
  --credentials-file=/credentials.json --address=0.0.0.0 --port=5432 \
  ai-lab-502500:us-central1:enterprise-portal-db
.venv/bin/python deploy/issue_cloud_tokens.py
docker rm -f enterprise-cloud-sql-proxy
```

The script gets the database URL from Secret Manager, issues 24-hour tokens for the three allowlisted accounts, and writes them with 0600 permissions without printing tokens. Issuing new tokens does not revoke older ones; they expire normally. For immediate revocation, use `backend.app.demo revoke-mcp-token` against the cloud database with the credential ID, following the same protected proxy setup.

## Repeat a deployment

The infrastructure is already provisioned. Enable these APIs when provisioning another project: Cloud Run, Cloud Build, Artifact Registry, Cloud SQL Admin, and Secret Manager. Create the PostgreSQL instance/database/user and the database URL secret before deploying. The runtime identity needs `roles/cloudsql.client` and secret-scoped `roles/secretmanager.secretAccessor`; it does not need the deployment service account's broad permissions.

Build a fresh image tag rather than replacing an existing tag:

```sh
gcloud builds submit --project=ai-lab-502500 --region=us-central1 \
  --config=deploy/cloudbuild.yaml --substitutions=_TAG=YOUR_NEW_TAG
.venv/bin/python deploy/render_cloudrun.py \
  --project ai-lab-502500 --number 265050340558 --tag YOUR_NEW_TAG \
  --portal-url https://enterprise-portal-q7la2lmmlq-uc.a.run.app \
  --mcp-url https://enterprise-mcp-q7la2lmmlq-uc.a.run.app
gcloud run jobs replace .secrets/cloudrun/init.json --project=ai-lab-502500 --region=us-central1
gcloud run jobs execute enterprise-portal-init --project=ai-lab-502500 --region=us-central1 --wait
gcloud run services replace .secrets/cloudrun/portal.json --project=ai-lab-502500 --region=us-central1
gcloud run services replace .secrets/cloudrun/mcp.json --project=ai-lab-502500 --region=us-central1
```

The renderer writes manifests containing secret references, never secret values. The initialization job applies migrations and seeds reference data with `--no-samples`; repeat execution preserves existing workflow records. Cloud Run remains private unless its IAM policy is explicitly changed. Initialization and service health were verified in the live project.

Runtime limits are one worker per MCP instance, maximum two instances per service, and zero minimum instances. Cloud SQL is a small zonal `db-f1-micro` Enterprise instance with 10 GB SSD and daily backups. **Cloud SQL incurs ongoing cost even when Cloud Run is idle.** Deleting the Cloud Run services does not stop that database cost. Manage or remove only these dedicated resources when the demo is no longer needed; other AI Lab applications were left untouched.

## Verification

The release gate passed **164 backend/MCP/PostgreSQL tests**, TypeScript checks, and **18 production browser tests**. Added checks cover the explicit proxy-origin allowlist, unchanged CSRF enforcement, rejection of unrelated origins, and repeatable reference-only seeding. Deployment scripts are included in the normal lint gate.

Live cloud checks passed:

- Both anonymous Cloud Run requests returned 403; authenticated MCP readiness returned 200.
- Missing or invalid application MCP credentials returned 401; an unrelated Origin returned 403.
- The cloud REST API returned all six personas; MCP advertised exactly 33 tools.
- Dinesh logged seven Compression Engine hours without a description, retried the same creation without duplicating the entry, and submitted the sheet. Gilfoyle approved it.
- A task assigned to Dinesh was completed. Leave was requested and rejected with the required feedback.
- A ticket was created, assigned, closed directly, and reopened.
- Directory, historical timesheets, pending approvals, and MCP activity were accessible.
- Manager self-approval, employee ticket assignment, and unauthorized leave access failed as expected. Richard approved the manager's leave.
- Through the IAM proxy, the real cloud UI automatically displayed the approved seven-hour timesheet, DONE task, assigned OPEN ticket, rejected leave and its feedback, and MCP success/denial audit events.

Screenshot evidence: [cloud timesheet](test-evidence/cloud-timesheet-2026-10-05.png). Temporary verification workflow records were removed after checking the UI, leaving users, projects, and credentials intact for a fresh demonstration.

Initial Cloud Build: `48adaf68-7ed4-431e-b61a-0d67d5325506`; image tag `20261005-v1`. Initialization execution: `enterprise-portal-init-mwltj` (successful). The copied key and cloud tokens remain only in ignored private local files.
