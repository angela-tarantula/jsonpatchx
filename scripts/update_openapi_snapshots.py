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

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # predictable absolute imports

# pylint: disable=wrong-import-position
from examples.loader import DEMO_MAP  # noqa: E402


def main() -> None:
    """Write all generated OpenAPI snapshot files."""
    for demo in DEMO_MAP.values():
        path = demo.snapshot_path
        schema = demo.app.openapi()

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")

        print(f"wrote {path}")


if __name__ == "__main__":
    main()
