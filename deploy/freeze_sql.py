"""Briefly freeze SQL writes for final export; migration-only operator command."""

import argparse
from pathlib import Path
from sqlalchemy import create_engine, text

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["freeze", "unfreeze"])
    parser.add_argument("--url-file", type=Path, required=True)
    args = parser.parse_args()
    engine = create_engine(args.url_file.read_text().strip())
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as db:
        if args.action == "freeze":
            busy = db.scalar(
                text(
                    "SELECT count(*) FROM chat_conversations WHERE busy_until + interval '2 minutes' > now()"
                )
            )
            if busy:
                raise SystemExit("Active agent turns must finish before cutover")
            db.execute(text("ALTER DATABASE portal SET default_transaction_read_only = on"))
        else:
            db.execute(text("SET default_transaction_read_only = off"))
            db.execute(text("ALTER DATABASE portal SET default_transaction_read_only = off"))
        db.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'portal' AND usename = current_user AND pid <> pg_backend_pid()"
            )
        )
    print("SQL write freeze " + ("enabled" if args.action == "freeze" else "disabled"))
