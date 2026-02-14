from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from examples.fastapi import demo1, demo2, demo3, demo4  # noqa: E402
from tests.integration.test_openapi_snapshot import (  # noqa: E402
    SNAPSHOT_PATH,
    _build_openapi,
)


def _write_snapshot(path: Path, schema: object) -> None:
    path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {path}")


def main() -> None:
    snapshot_dir = ROOT / "tests" / "integration" / "fastapi_tests" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    _write_snapshot(snapshot_dir / "demo1_openapi.json", demo1.app.openapi())
    _write_snapshot(snapshot_dir / "demo2_openapi.json", demo2.app.openapi())
    _write_snapshot(snapshot_dir / "demo3_openapi.json", demo3.app.openapi())
    _write_snapshot(snapshot_dir / "demo4_openapi.json", demo4.app.openapi())
    _write_snapshot(SNAPSHOT_PATH, _build_openapi())


if __name__ == "__main__":
    main()
