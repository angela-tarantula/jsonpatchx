from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from contextlib import suppress

from examples.loader import DEMO_MAP, Demo


def run_demo(demo: Demo) -> None:
    print(f"\n--- Launching {demo.name} ---")

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        demo.app_path,
        "--port",
        str(demo.port),
        "--reload",
    ]
    proc = subprocess.Popen(cmd, start_new_session=True)
    print(f"Swagger: http://127.0.0.1:{demo.port}/docs")

    print("\nPress Ctrl+C to stop the server...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        with suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
        print("\nServer stopped.")


def main() -> None:
    print("Available demos:")
    for demo_id, demo in DEMO_MAP.items():
        print(f"  {demo_id}) {demo.name} (port {demo.port})")

    choice = input("\nSelect a demo (1-7): ").strip()
    if choice not in DEMO_MAP:
        print("Invalid choice.")
        return
    run_demo(DEMO_MAP[choice])


if __name__ == "__main__":
    main()
