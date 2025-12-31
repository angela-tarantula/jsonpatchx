"""
CLI demo: custom ops with a custom registry.

Run:
  python -m examples.custom.cli_apply
"""

from __future__ import annotations

import json

from examples.custom_ops import IncrementOp, ToggleBoolOp
from jsonpatch import JsonPatch, OperationRegistry
from jsonpatch.types import JSONValue


def main() -> None:
    doc: JSONValue = {"trial": False, "quota": 3}
    patch_ops: list[dict[str, JSONValue]] = [
        {"op": "increment", "path": "/quota", "value": 2},
        {"op": "toggle", "path": "/trial"},
    ]

    registry = OperationRegistry.with_standard(IncrementOp, ToggleBoolOp)
    patch = JsonPatch(patch_ops, registry=registry)
    updated = patch.apply(doc)

    print("original:", json.dumps(doc))
    print("patched:", json.dumps(updated))


if __name__ == "__main__":
    main()
