# Pied Piper ADK chat

The chat service uses **Google ADK 2.11.0**, **Gemini 3.8 Flash** through Vertex AI, and ADK's official `McpToolset` over Streamable HTTP. All business reads and writes go through the existing deployed MCP server; the chat service does not implement a second set of business tools.

Cloud service: https://enterprise-chat-q7la2lmmlq-uc.a.run.app

The service is private behind Cloud Run IAM, like the enterprise portal. For a browser demonstration, start an authenticated proxy:

```sh
export CLOUDSDK_CONFIG="$PWD/.gcloud"
gcloud auth activate-service-account --key-file=ai-lab-fasa.json --project=ai-lab-502500
gcloud run services proxy enterprise-chat --project=ai-lab-502500 --region=us-central1 --port=3400
```

Open **http://localhost:3400**. Start the portal proxy on port 3300 from [DEPLOYMENT.md](DEPLOYMENT.md) if you want to watch records change beside the chat.

## Profiles and example requests

Select a profile; no token copying or tool names are needed. The six allowlisted seeded profiles are Richard, Gilfoyle, Monica, Dinesh, Jared, and Erlich. This is a protected internal demo: anyone granted access to the chat service can select its demo personas. It is not real employee sign-in.

Try these across independent conversations:

1. **Dinesh:** “Who am I, who is my manager, and which projects can I log time to?”
2. **Dinesh:** “Log seven hours on Compression Engine today, without a description.”
3. **Dinesh:** “Submit my timesheet for this week.”
4. **Gilfoyle:** “Show requests waiting for my approval, then approve Dinesh’s timesheet for this week.”
5. **Gilfoyle:** “Create a task assigned to Dinesh called Investigate compression performance.”
6. **Dinesh:** “Mark my Investigate compression performance task done.”
7. **Dinesh:** “Request leave for October 19–21, 2026.”
8. **Gilfoyle:** “Reject Dinesh’s October 19–21 leave request because team coverage is required.”
9. **Dinesh:** “Open a high-priority support ticket called VPN connection failure.”
10. **Richard:** “Assign Dinesh’s VPN connection failure ticket to Jared.”
11. **Jared:** “Close the VPN connection failure ticket assigned to me.”
12. **Richard:** “Show recent MCP activity.”

Use unused dates or fresh names for repeated demos. Writes are real and commit individually; the agent reports permission failures or partial completion. It may ask for clarification when a name or record is ambiguous. Clear requests execute without a separate confirmation dialog. The portal refreshes workflow views automatically every ten seconds.

Switching profiles restores that profile's independent conversation in the same browser. Refreshing the page also restores it. **New chat** starts an empty conversation for the selected profile. It does not delete enterprise records or audit events. **Sign out** expires the selected profile's chat session. Profile conversations do not share model history, credentials, or identity. Chats can also run in separate tabs or browser profiles.

## Authentication and persistence

- The deployment service account is used only for provisioning. Cloud Run uses a dedicated `enterprise-chat-runtime` workload identity; no JSON key is deployed.
- The runtime has Vertex AI user, Cloud SQL client, scoped database-secret access, and invocation access to the existing MCP service.
- Selecting a profile creates an eight-hour HttpOnly, SameSite Strict chat cookie. Origins and CSRF tokens protect authenticated writes. The browser never receives an MCP bearer token or Google identity token.
- Each turn reloads the account and creates an expiring MCP credential scoped to that profile. Review scope is issued only for managers/admins. The credential is revoked after the turn; an interrupted process leaves at most its one-hour lifetime.
- Google identity tokens are obtained server-side per turn for Cloud Run invocation. The MCP server still resolves the active account and enforces all existing permissions.
- Conversations, complete ADK events, and turn results persist in PostgreSQL. Stored events retain model/tool context across refreshes and Cloud Run instance changes. Thought content/signatures are not shown in the browser.
- A conversation row lock admits one running turn. The client supplies a UUID turn key; identical completed retries return the saved response without repeating agent actions, and changed-input reuse conflicts. Creation tool keys are bound to the turn and business arguments.
- Interrupted turns are not silently retried. Start a new chat and check records before repeating a write. Each conversation is limited to thirty turns, each turn to sixteen model calls and a six-minute model/tool execution budget.
- Record text is untrusted input. Prompts, raw credentials, tool arguments, and raw error traces are not included in the application's operational logging. Assistant text is rendered as text, never executed HTML.

## Build, deploy and test

Install chat dependencies separately from the portal/MCP dependencies:

```sh
python3 -m venv .venv-chat
.venv-chat/bin/pip install -r chat_app/requirements.txt pytest==9.0.2
.venv-chat/bin/python -m pytest -q chat_app/tests
```

`make check`, `make verify`, and GitHub CI include the chat suite. It covers persona isolation, allowlisting, role/source spoofing, credential kinds, cookie security, CSRF/origins, persistent history, failed-turn replay, logout, and concurrent PostgreSQL turns. The existing backend/MCP and browser suites remain intact.

Build and deploy with a fresh tag:

```sh
gcloud builds submit --project=ai-lab-502500 --region=us-central1 \
  --config=deploy/chat-cloudbuild.yaml --substitutions=_TAG=YOUR_NEW_TAG
.venv/bin/python deploy/render_cloudrun.py --project ai-lab-502500 --number 265050340558 \
  --tag YOUR_NEW_TAG --portal-url https://enterprise-portal-q7la2lmmlq-uc.a.run.app \
  --mcp-url https://enterprise-mcp-q7la2lmmlq-uc.a.run.app
gcloud run jobs replace .secrets/cloudrun/init.json --project=ai-lab-502500 --region=us-central1
gcloud run jobs execute enterprise-portal-init --project=ai-lab-502500 --region=us-central1 --wait
.venv/bin/python deploy/render_chat.py --tag YOUR_NEW_TAG
gcloud run services replace .secrets/cloudrun/chat.json --project=ai-lab-502500 --region=us-central1
```

The chat build also produces the backend image for migrations. It does not redeploy the portal or MCP service. The runtime uses the database URL secret, `GOOGLE_GENAI_USE_VERTEXAI=true`, project `ai-lab-502500`, global model location, and an explicit browser origin allowlist. Maximum two instances, concurrency four, one worker, zero minimum instances. Model requests incur Vertex AI usage charges in addition to the existing cloud database/runtime costs.

Public employee-facing deployment still requires real sign-in and an identity-to-account mapping. Do not make the persona selector publicly accessible.
