"""Render the private Cloud Run ADK chat service with workload identity."""

import argparse
import json
from pathlib import Path


def render(project, number, tag, url, output):
    region = "us-central1"
    spec = {
        "apiVersion": "serving.knative.dev/v1",
        "kind": "Service",
        "metadata": {
            "name": "enterprise-chat",
            "labels": {"cloud.googleapis.com/location": region},
        },
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "run.googleapis.com/cloudsql-instances": f"{project}:{region}:enterprise-portal-db",
                        "run.googleapis.com/execution-environment": "gen2",
                        "autoscaling.knative.dev/maxScale": "2",
                    }
                },
                "spec": {
                    "serviceAccountName": f"enterprise-chat-runtime@{project}.iam.gserviceaccount.com",
                    "containerConcurrency": 4,
                    "timeoutSeconds": 420,
                    "containers": [
                        {
                            "image": f"{region}-docker.pkg.dev/{project}/cloud-run-source-deploy/enterprise-chat:{tag}",
                            "ports": [{"containerPort": 8080}],
                            "resources": {"limits": {"cpu": "1000m", "memory": "1Gi"}},
                            "startupProbe": {
                                "httpGet": {"path": "/health", "port": 8080},
                                "periodSeconds": 5,
                                "failureThreshold": 24,
                            },
                            "env": [
                                {
                                    "name": "DATABASE_URL",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "enterprise-portal-database-url",
                                            "key": "1",
                                        }
                                    },
                                },
                                {"name": "DEMO_MODE", "value": "true"},
                                {"name": "SECURE_COOKIES", "value": "true"},
                                {"name": "GOOGLE_GENAI_USE_VERTEXAI", "value": "true"},
                                {"name": "GOOGLE_CLOUD_PROJECT", "value": project},
                                {"name": "GOOGLE_CLOUD_LOCATION", "value": "global"},
                                {
                                    "name": "CHAT_ALLOWED_ORIGINS",
                                    "value": ",".join(
                                        [
                                            url,
                                            f"https://enterprise-chat-{number}.{region}.run.app",
                                            "http://localhost:3400",
                                            "http://127.0.0.1:3400",
                                        ]
                                    ),
                                },
                                {
                                    "name": "CHAT_MCP_URL",
                                    "value": "https://enterprise-mcp-q7la2lmmlq-uc.a.run.app/mcp",
                                },
                            ],
                        }
                    ],
                },
            }
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="ai-lab-502500")
    parser.add_argument("--number", default="265050340558")
    parser.add_argument("--tag", required=True)
    parser.add_argument("--url", default="https://enterprise-chat-q7la2lmmlq-uc.a.run.app")
    parser.add_argument("--output", type=Path, default=Path(".secrets/cloudrun/chat.json"))
    args = parser.parse_args()
    render(args.project, args.number, args.tag, args.url, args.output)
