"""Issue cloud demo credentials through a temporary Cloud SQL proxy; never print tokens."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="ai-lab-502500")
    parser.add_argument("--proxy-port", type=int, default=5434)
    parser.add_argument("--gcloud", default="gcloud")
    parser.add_argument("--output", type=Path, default=Path(".secrets/cloud-personas.json"))
    args = parser.parse_args()
    secret = subprocess.check_output(
        [
            args.gcloud,
            "secrets",
            "versions",
            "access",
            "latest",
            "--secret=enterprise-portal-database-url",
            f"--project={args.project}",
        ],
        text=True,
    ).strip()
    url = make_url(secret).set(host="127.0.0.1", port=args.proxy_port, query={})
    os.environ["DATABASE_URL"] = url.render_as_string(hide_password=False)
    os.environ["DEMO_MODE"] = "true"
    from backend.app.auth.tokens import issue_mcp_token

    records = {}
    for name, number, review in [("dinesh", 2, False), ("gilfoyle", 1, True), ("richard", 6, True)]:
        scopes = ["portal:read", "portal:write"] + (["portal:review"] if review else [])
        token, credential = issue_mcp_token(
            UUID(f"00000000-0000-4000-8000-{number:012d}"), scopes, 24
        )
        records[name] = {"token": token, "credential_id": str(credential)}
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Set permissions before writing sensitive content, including when replacing an existing file.
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(descriptor, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(records, stream, indent=2)
    print(f"Saved three cloud persona credentials to {args.output}; valid for 24 hours.")


if __name__ == "__main__":
    main()
