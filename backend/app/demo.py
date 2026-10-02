import argparse
import json
from uuid import UUID
from backend.app.config import settings
from backend.app.database.seed import seed
from backend.app.auth.tokens import issue_mcp_token, revoke_mcp_credential
from backend.app.auth.context import ServiceError


def main():
    parser = argparse.ArgumentParser(description="Local demo administration")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("seed")
    issue = commands.add_parser("issue-mcp-token")
    issue.add_argument("--user-id", type=UUID, required=True)
    issue.add_argument("--scope", action="append", dest="scopes")
    issue.add_argument("--hours", type=float, default=8)
    revoke = commands.add_parser("revoke-mcp-token")
    revoke.add_argument("--credential-id", type=UUID, required=True)
    args = parser.parse_args()
    if not settings.demo_mode:
        parser.error("Set DEMO_MODE=true explicitly to enable demo administration")
    try:
        if args.command == "seed":
            seed()
            print("Demo data seeded.")
        elif args.command == "issue-mcp-token":
            token, credential_id = issue_mcp_token(args.user_id, args.scopes, args.hours)
            print(json.dumps({"token": token, "credential_id": str(credential_id)}))
        else:
            revoke_mcp_credential(args.credential_id)
            print("MCP credential revoked.")
    except ServiceError as exc:
        parser.error(exc.message)


if __name__ == "__main__":
    main()
