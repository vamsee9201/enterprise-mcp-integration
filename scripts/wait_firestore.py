"""Wait for the local emulator without cloud credentials or writes."""

import os
import socket
import time

host, port = os.environ.get("FIRESTORE_EMULATOR_HOST", "127.0.0.1:8787").rsplit(":", 1)
for attempt in range(60):
    try:
        with socket.create_connection((host, int(port)), timeout=1):
            break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("Firestore emulator did not become ready")
