import argparse
from backend.app.config import settings
from backend.app.database.seed import seed


def main():
    parser = argparse.ArgumentParser(description="Local demo administration")
    parser.add_argument("command", choices=["seed"])
    parser.parse_args()
    if not settings.demo_mode:
        parser.error("Set DEMO_MODE=true explicitly to enable demo administration")
    seed()
    print("Demo data seeded.")


if __name__ == "__main__":
    main()
