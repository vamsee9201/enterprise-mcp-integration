"""Issue cloud demo credentials through a Firestore workload credentials; never print tokens."""

import argparse
import json
import os
import sys
from pathlib import Path
from uuid import UUID


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="ai-lab-502500")
    parser.add_argument("--database", default="enterprise-portal")
    parser.add_argument("--output", type=Path, default=Path(".secrets/cloud-personas.json"))
    args = parser.parse_args()
    os.environ["FIRESTORE_PROJECT"] = args.project
    os.environ["FIRESTORE_DATABASE"] = args.database
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
