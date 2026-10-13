# Private Cloud Run deployment

The portal, MCP server and ADK chat run in `ai-lab-502500`, region `us-central1`, with Firestore database `enterprise-portal`. Cloud SQL has been retired. See [Firestore setup, transactions and recovery](FIRESTORE.md) and [verification evidence](FIRESTORE_TEST_REPORT.md).

| Service | Private URL |
|---|---|
| Portal | https://enterprise-portal-q7la2lmmlq-uc.a.run.app/ |
| MCP | https://enterprise-mcp-q7la2lmmlq-uc.a.run.app/mcp |
| Chat | https://enterprise-chat-q7la2lmmlq-uc.a.run.app/ |

Direct browser access without Cloud Run invocation credentials returns 403. Use an authenticated Google Cloud CLI account with invocation access:

```sh
gcloud run services proxy enterprise-portal --project=ai-lab-502500 --region=us-central1 --port=3300
gcloud run services proxy enterprise-chat --project=ai-lab-502500 --region=us-central1 --port=3400
```

Run each proxy in its own terminal. Open http://localhost:3300 and http://localhost:3400. Cookies/CSRF and persona permissions remain enforced behind the IAM proxy.

## Build and deploy

Use a deployment identity authorized for this project. Never put a service-account key in Git, build contexts or containers. Configure `CLOUDSDK_CONFIG` in an isolated directory and use Application Default Credentials for operator Firestore scripts. Cloud containers authenticate with workload identity.

Build `deploy/cloudbuild.yaml` and `deploy/chat-cloudbuild.yaml` with the same `_TAG` substitution. Render manifests:

```sh
.venv/bin/python deploy/render_cloudrun.py --project ai-lab-502500 --number 265050340558 --tag YOUR_TAG --portal-url https://enterprise-portal-q7la2lmmlq-uc.a.run.app --mcp-url https://enterprise-mcp-q7la2lmmlq-uc.a.run.app
.venv/bin/python deploy/render_chat.py --tag YOUR_TAG
gcloud run services replace .secrets/cloudrun/mcp.json --project=ai-lab-502500 --region=us-central1
gcloud run services replace .secrets/cloudrun/chat.json --project=ai-lab-502500 --region=us-central1
gcloud run services replace .secrets/cloudrun/portal.json --project=ai-lab-502500 --region=us-central1
gcloud run jobs replace .secrets/cloudrun/init.json --project=ai-lab-502500 --region=us-central1
```

The initialization job seeds reference data only and preserves existing workflows. No SQL migrations, database password secrets, Cloud SQL sockets or VPC connector are needed. The named Firestore database already exists; do not provision another one on each release.

Portal/MCP identity: `enterprise-portal-runtime@ai-lab-502500.iam.gserviceaccount.com`. Chat identity: `enterprise-chat-runtime@ai-lab-502500.iam.gserviceaccount.com`. Both have database-scoped Firestore access. Chat retains Vertex AI access and invocation access to MCP. No public invocation grant is added. Services have zero minimum and two maximum instances.

To issue cloud MCP credentials, set `GOOGLE_APPLICATION_CREDENTIALS` for a trusted local operator (or use ADC), then run `deploy/issue_cloud_tokens.py`. Tokens are saved in a 0600 ignored file; they are never build inputs. `deploy/cloud_demo.py` demonstrates the protected endpoint with those credentials and a Cloud Run identity token. Select an empty Monday-start week because this script creates real workflow records.

Firestore, model calls, builds, image storage and the private recovery bucket are usage-billed. The named database has no default-database free quota. There is no always-running SQL instance. Budget alerts are notifications, not spending caps.
