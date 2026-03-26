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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# pylint: disable=wrong-import-position
from examples.loader import (  # noqa: E402
    DEMO_MAP,
)


def _write_snapshot(path: Path, schema: object) -> None:
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {path}")


def main() -> None:
    """Write all generated OpenAPI snapshot files."""
    demos = tuple(DEMO_MAP.values())
    snapshot_paths = [spec.snapshot_path for spec in demos]
    for path in snapshot_paths:
        path.parent.mkdir(parents=True, exist_ok=True)

    snapshot_schemas = [spec.app.openapi() for spec in demos]

    for path, schema in zip(snapshot_paths, snapshot_schemas, strict=True):
        _write_snapshot(path, schema)


if __name__ == "__main__":
    main()
