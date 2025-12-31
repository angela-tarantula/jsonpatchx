from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

DEMOS: dict[str, tuple[str, str, int]] = {
    "1": ("The standard model patch", "examples.standard.api_typed_model:app", 8000),
    "2": ("Untyped document patching", "examples.standard.api_untyped_doc:app", 8001),
    "3": (
        "First-class custom operations",
        "examples.custom_ops.api_custom_ops_typed:app",
        8002,
    ),
    "4": (
        "Custom ops + Pydantic models",
        "examples.custom_ops.api_custom_ops_model:app",
        8003,
    ),
    "5": (
        "Custom pointer backends",
        "examples.pointer_backends.api_custom_pointer:app",
        8004,
    ),
}


def run_demo(choice: str) -> None:
    name, app_path, port = DEMOS[choice]
    print(f"\n--- Launching {name} ---")

    cmd = [sys.executable, "-m", "uvicorn", app_path, "--port", str(port), "--reload"]
    proc = subprocess.Popen(cmd, start_new_session=True)
    print(f"Swagger: http://127.0.0.1:{port}/docs")

    print("\nPress Ctrl+C to stop the server...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        try:
            os.killpg(proc.pid, signal.SIGINT)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
        print("\nServer stopped.")


def main() -> None:
    print("Available demos:")
    for key, (label, _, port) in DEMOS.items():
        print(f"  {key}) {label} (port {port})")

    choice = input("\nSelect a demo (1-5): ").strip()
    if choice not in DEMOS:
        print("Invalid choice.")
        return
    run_demo(choice)


if __name__ == "__main__":
    main()
