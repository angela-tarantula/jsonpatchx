"""
CLI demo: build a JsonPatch and apply it to a document.

Run:
  python -m examples.standard.cli_apply
"""

from __future__ import annotations

import json

from jsonpatch import JsonPatch, apply_patch
from jsonpatch.types import JSONValue


def main() -> None:
    doc: JSONValue = {"title": "Example", "tags": ["admin", "staff"]}
    patch_ops_list: list[dict[str, JSONValue]] = [
        {"op": "replace", "path": "/title", "value": "Updated"},
        {"op": "add", "path": "/tags/-", "value": "qa"},
    ]
    patch_json_string = json.dumps(patch_ops_list)

    patch = JsonPatch(patch_ops_list)
    patch_from_json = JsonPatch.from_string(patch_json_string)
    assert patch == patch_from_json

    updated = patch.apply(doc)
    updated_alt = apply_patch(doc, patch_ops_list)

    print("original:", json.dumps(doc))
    print("patched:", json.dumps(updated))
    print("patched (apply_patch):", json.dumps(updated_alt))


if __name__ == "__main__":
    main()
