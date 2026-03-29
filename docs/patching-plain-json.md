# Patching Plain JSON

Use this when your target is a plain JSON document (`dict`/`list`) and you do
not need API request-model generation.

## Option A: `apply_patch` Convenience

```python
from jsonpatchx import apply_patch

doc = {"service": {"enabled": False, "max_users": 100}}
patch = [
    {"op": "replace", "path": "/service/enabled", "value": True},
    {"op": "replace", "path": "/service/max_users", "value": 200},
]

updated = apply_patch(doc, patch)
```

Pass `inplace=True` to apply directly against the input object.

## Option B: `JsonPatch` Object

```python
from jsonpatchx import JsonPatch

patch = JsonPatch(
    [
        {"op": "replace", "path": "/service/enabled", "value": True},
        {"op": "replace", "path": "/service/max_users", "value": 200},
    ]
)

updated = patch.apply({"service": {"enabled": False, "max_users": 100}})
```

Use this when you want to validate once and reapply many times.

## When To Move Beyond This

If you are building PATCH HTTP endpoints and want OpenAPI request contracts, use
[FastAPI Integration](fastapi-integration.md) with
[JsonPatchFor Contracts](jsonpatchfor-contracts.md).
