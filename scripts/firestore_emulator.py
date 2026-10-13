"""Local-only emulator runner: save a snapshot before forwarding shutdown.

Google's emulator export endpoint requires an existing output directory. Import
uses the generated metadata file. Production never executes this helper.
"""

import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.request import Request, urlopen

project = os.environ.get("FIRESTORE_PROJECT", "demo-enterprise-portal")
directory = Path("/data/export")
metadata = directory / "firestore_export" / "firestore_export.overall_export_metadata"
command = ["gcloud", "emulators", "firestore", "start", "--host-port=0.0.0.0:8787", "--quiet"]
if metadata.exists():
    command.append("--import-data=" + str(metadata))
process = subprocess.Popen(command, start_new_session=True)
stopping = False


def stop(signum, frame):
    global stopping
    stopping = True


signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
while process.poll() is None and not stopping:
    time.sleep(0.2)
if stopping:
    directory.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(
        {
            "database": f"projects/{project}/databases/(default)",
            "export_directory": str(directory),
            "export_name": "firestore_export",
        }
    ).encode()
    request = Request(
        f"http://127.0.0.1:8787/emulator/v1/projects/{project}:export",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=25) as response:
            if response.status != 200:
                raise RuntimeError("Emulator export failed")
        print("Local Firestore snapshot saved.", flush=True)
    finally:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
else:
    raise SystemExit(process.returncode)
