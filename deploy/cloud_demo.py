"""Run the existing MCP demonstration against the IAM-protected cloud service."""

import argparse
import asyncio
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.mcp_demo import demonstrate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://enterprise-mcp-q7la2lmmlq-uc.a.run.app")
    parser.add_argument("--gcloud", default="gcloud")
    parser.add_argument("--credentials", type=Path, default=Path(".secrets/cloud-personas.json"))
    parser.add_argument(
        "--week", type=date.fromisoformat, required=True, help="An empty Monday-start week"
    )
    args = parser.parse_args()
    if args.week.weekday() != 0:
        parser.error("Choose a Monday")
    identity = subprocess.check_output(
        [args.gcloud, "auth", "print-identity-token", f"--audiences={args.url}"], text=True
    ).strip()
    personas = json.loads(args.credentials.read_text())
    result = asyncio.run(
        demonstrate(
            args.url + "/mcp",
            *(personas[name]["token"] for name in ["dinesh", "gilfoyle", "richard"]),
            args.week,
            identity,
        )
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
