from __future__ import annotations

from jsonpatch.types import JSONValue

INVALID_POINTER_PATCH: list[dict[str, JSONValue]] = [
    {"op": "add", "path": "not-a-pointer", "value": 1}
]

TYPE_GATED_INCREMENT_PATCH: list[dict[str, JSONValue]] = [
    {"op": "increment", "path": "/title", "value": 4.5}
]

OUT_OF_RANGE_REMOVE_PATCH: list[dict[str, JSONValue]] = [
    {"op": "remove", "path": "/tags/999"}
]

TEST_FAILS_PATCH: list[dict[str, JSONValue]] = [
    {"op": "test", "path": "/trial", "value": True}
]

EXPLODE_PATCH: list[dict[str, JSONValue]] = [{"op": "explode", "path": "/title"}]
