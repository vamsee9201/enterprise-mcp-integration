"""Render secret-reference-only Cloud Run manifests for the protected demo."""

import argparse
import json
from pathlib import Path


def render(project, number, region, tag, output, portal_url=None, mcp_url=None):
    registry = f"{region}-docker.pkg.dev/{project}/cloud-run-source-deploy"
    backend = f"{registry}/enterprise-backend:{tag}"
    frontend = f"{registry}/enterprise-frontend:{tag}"
    runtime = f"enterprise-portal-runtime@{project}.iam.gserviceaccount.com"
    database = f"{project}:{region}:enterprise-portal-db"
    portal_url = portal_url or f"https://enterprise-portal-{number}.{region}.run.app"
    mcp_url = mcp_url or f"https://enterprise-mcp-{number}.{region}.run.app"
    common = [
        {
            "name": "DATABASE_URL",
            "valueFrom": {"secretKeyRef": {"name": "enterprise-portal-database-url", "key": "1"}},
        },
        {"name": "DEMO_MODE", "value": "true"},
        {"name": "WEB_ORIGIN", "value": portal_url},
        {
            "name": "WEB_ALLOWED_ORIGINS",
            "value": json.dumps(
                [
                    f"https://enterprise-portal-{number}.{region}.run.app",
                    "http://localhost:3300",
                    "http://127.0.0.1:3300",
                ]
            ),
        },
        {"name": "SECURE_COOKIES", "value": "true"},
    ]

    def service(name, containers, dependencies=None):
        annotations = {
            "run.googleapis.com/cloudsql-instances": database,
            "run.googleapis.com/execution-environment": "gen2",
            "autoscaling.knative.dev/maxScale": "2",
        }
        if dependencies:
            annotations["run.googleapis.com/container-dependencies"] = json.dumps(dependencies)
        return {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {"name": name, "labels": {"cloud.googleapis.com/location": region}},
            "spec": {
                "template": {
                    "metadata": {"annotations": annotations},
                    "spec": {
                        "serviceAccountName": runtime,
                        "containerConcurrency": 20,
                        "timeoutSeconds": 300,
                        "containers": containers,
                    },
                }
            },
        }

    def resources():
        return {"limits": {"cpu": "1000m", "memory": "512Mi"}}

    backend_container = {
        "name": "backend",
        "image": backend,
        "env": common,
        "resources": resources(),
        "startupProbe": {
            "httpGet": {"path": "/health", "port": 8000},
            "periodSeconds": 5,
            "failureThreshold": 24,
        },
    }
    frontend_container = {
        "name": "frontend",
        "image": frontend,
        "ports": [{"containerPort": 3000}],
        "resources": resources(),
        "startupProbe": {"tcpSocket": {"port": 3000}, "periodSeconds": 5, "failureThreshold": 24},
    }
    mcp_container = {
        "name": "mcp",
        "image": backend,
        "ports": [{"containerPort": 8080}],
        "command": ["uvicorn"],
        "args": ["mcp_server.asgi:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"],
        "env": common
        + [
            {"name": "MCP_AUTH_MODE", "value": "demo"},
            {"name": "MCP_PUBLIC_URL", "value": mcp_url + "/mcp"},
            {
                "name": "MCP_ALLOWED_HOSTS",
                "value": json.dumps(
                    [
                        mcp_url.removeprefix("https://"),
                        f"enterprise-mcp-{number}.{region}.run.app",
                        "localhost:8080",
                        "127.0.0.1:8080",
                    ]
                ),
            },
            {
                "name": "MCP_ALLOWED_ORIGINS",
                "value": json.dumps([portal_url, "http://localhost:3300", "http://localhost:6274"]),
            },
        ],
        "resources": resources(),
        "startupProbe": {
            "httpGet": {"path": "/ready", "port": 8080},
            "periodSeconds": 5,
            "failureThreshold": 24,
        },
    }
    job = {
        "apiVersion": "run.googleapis.com/v1",
        "kind": "Job",
        "metadata": {"name": "enterprise-portal-init"},
        "spec": {
            "template": {
                "metadata": {"annotations": {"run.googleapis.com/cloudsql-instances": database}},
                "spec": {
                    "template": {
                        "spec": {
                            "serviceAccountName": runtime,
                            "maxRetries": 0,
                            "timeoutSeconds": "300",
                            "containers": [
                                {
                                    "image": backend,
                                    "env": common,
                                    "resources": resources(),
                                    "command": ["sh"],
                                    "args": [
                                        "-c",
                                        "alembic -c backend/alembic.ini upgrade head && python -m backend.app.demo seed --no-samples",
                                    ],
                                }
                            ],
                        },
                    }
                },
            }
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    for name, spec in [
        (
            "portal",
            service(
                "enterprise-portal",
                [frontend_container, backend_container],
                {"frontend": ["backend"]},
            ),
        ),
        ("mcp", service("enterprise-mcp", [mcp_container])),
        ("init", job),
    ]:
        (output / f"{name}.json").write_text(json.dumps(spec, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("--number", required=True)
    parser.add_argument("--region", default="us-central1")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--output", type=Path, default=Path(".secrets/cloudrun"))
    parser.add_argument("--portal-url")
    parser.add_argument("--mcp-url")
    args = parser.parse_args()
    render(
        args.project, args.number, args.region, args.tag, args.output, args.portal_url, args.mcp_url
    )
