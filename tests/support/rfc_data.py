from __future__ import annotations

import importlib.resources as resources
import json
from typing import Any


def load_json_records(package: str, filenames: tuple[str, ...]) -> list[dict[str, Any]]:
    """Load and concatenate JSON object arrays from packaged test data files."""
    records: list[dict[str, Any]] = []
    data_root = resources.files(package)
    for filename in filenames:
        with (data_root / filename).open(encoding="utf8") as fd:
            records.extend(json.load(fd))
    return records
