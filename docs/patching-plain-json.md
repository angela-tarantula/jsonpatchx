# Patching Plain JSON

Use this page when patching JSON documents at runtime without FastAPI
request-model generation.

## Entry Points

| Need                       | API                           |
| -------------------------- | ----------------------------- |
| One-off patch apply        | `apply_patch(doc, patch)`     |
| Parse once and reuse       | `JsonPatch(...).apply(doc)`   |
| Parse patch from JSON text | `JsonPatch.from_string(text)` |

## One-Off Application

```python
from jsonpatchx import apply_patch

doc = {"service": {"enabled": False, "max_users": 100}}
patch = [
    {"op": "replace", "path": "/service/enabled", "value": True},
    {"op": "replace", "path": "/service/max_users", "value": 200},
]

updated = apply_patch(doc, patch)
```

Default behavior is non-mutating (`inplace=False`).

## Parse Once, Apply Many

```python
from jsonpatchx import JsonPatch

patch = JsonPatch(
    [
        {"op": "replace", "path": "/tier", "value": "pro"},
        {"op": "replace", "path": "/limits/max_projects", "value": 25},
    ]
)

tenants = [
    {"tier": "free", "limits": {"max_projects": 3}},
    {"tier": "free", "limits": {"max_projects": 5}},
]

upgraded = [patch.apply(doc) for doc in tenants]
```

## Parse JSON Patch Text

```python
from jsonpatchx import JsonPatch

patch = JsonPatch.from_string('[{"op":"replace","path":"/enabled","value":true}]')
updated = patch.apply({"enabled": False})
```

## In-Place Apply

```python
from jsonpatchx import apply_patch

state = {"count": 1}
result = apply_patch(
    state,
    [{"op": "replace", "path": "/count", "value": 2}],
    inplace=True,
)
```

`inplace=True` is faster but non-transactional.

## Error Boundary Pattern

```python
from jsonpatchx import PatchConflictError, PatchValidationError, apply_patch

try:
    updated = apply_patch(doc, patch)
except PatchValidationError:
    handle_bad_patch_payload()
except PatchConflictError:
    handle_state_conflict()
```

## Scope Note

`JsonPatchFor` is for FastAPI PATCH contracts. Plain JSON patching should use
`apply_patch` or `JsonPatch`.
