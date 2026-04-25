"""Regenerate FastAPI OpenAPI snapshot fixtures used as API contract artifacts.

This repository treats generated OpenAPI as part of the product surface of
``JsonPatchX``. Committed snapshots make contract changes explicit in each PR
and commit, so reviewers can see exactly what API/schema behavior changed.

The snapshot files are derived artifacts, so they must be refreshed whenever
code or dependency updates affect generated OpenAPI. This script is used both:

- locally via pre-commit/``prek`` hooks, and
- in GitHub automation workflows (including Dependabot-triggered PR updates).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # predictable absolute imports

# pylint: disable=wrong-import-position
from examples.loader import DEMO_MAP  # noqa: E402


def write_snapshots() -> bool:
    """Write all generated OpenAPI snapshot files.

    Returns:
        True if any snapshot file content changed.
    """
    changed = False
    for demo in DEMO_MAP.values():
        path = demo.snapshot_path
        schema = demo.app.openapi()
        rendered = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        previous = path.read_text() if path.exists() else None

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered)
        if previous != rendered:
            changed = True

        print(f"wrote {path}")
    return changed


def main() -> int:
    """Write all generated OpenAPI snapshot files.

    Returns:
        Process exit code.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--exit-non-zero-on-format",
        action="store_true",
        help="Return exit code 1 when snapshot files were rewritten.",
    )
    args = parser.parse_args()

    changed = write_snapshots()
    if changed and args.exit_non_zero_on_format:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
