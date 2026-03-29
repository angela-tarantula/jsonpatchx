# Getting Started

This guide gets you to your first successful patch in a few minutes.

## Install

```sh
pip install jsonpatchx
```

## First Patch (Plain JSON)

```python
from jsonpatchx import apply_patch

doc = {"name": "Ada", "roles": ["engineer"]}
patch = [
    {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
    {"op": "add", "path": "/roles/-", "value": "maintainer"},
]

updated = apply_patch(doc, patch)
print(updated)
# {'name': 'Ada Lovelace', 'roles': ['engineer', 'maintainer']}
```

`apply_patch(...)` deep-copies by default, so `doc` is not mutated unless you
pass `inplace=True`.

## Parse Once, Apply Many

```python
from jsonpatchx import JsonPatch

patch = JsonPatch.from_string(
    """
    [
      {"op":"replace","path":"/name","value":"Ada Lovelace"},
      {"op":"add","path":"/roles/-","value":"maintainer"}
    ]
    """
)

updated = patch.apply({"name": "Ada", "roles": ["engineer"]})
```

Use `JsonPatch` when you want to parse/validate once and reapply to multiple
documents.

## Next Steps

1. Learn the data model in [Core Concepts](core-concepts.md).
2. Use typed model patching in
   [Patching Pydantic Models](patching-pydantic-models.md).
3. Add domain-specific operations in [Custom Operations](custom-operations.md).
