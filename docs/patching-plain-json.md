# Patching Plain JSON

Use this when your target is a plain JSON document (`dict`/`list`) instead of a
Pydantic model.

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

Pass `inplace=True` if you want to mutate `doc` directly.

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

Use this form when you want to reuse a validated patch object.

## Typed Request Model for Plain JSON APIs

For route contracts and OpenAPI generation, use `JsonPatchFor` with a
`Literal[...]` target name:

```python
from typing import Literal

from jsonpatchx import StandardRegistry
from jsonpatchx.pydantic import JsonPatchFor

ConfigPatch = JsonPatchFor[Literal["ServiceConfig"], StandardRegistry]
patch = ConfigPatch.model_validate(
    [{"op": "replace", "path": "/service/enabled", "value": True}]
)

updated = patch.apply({"service": {"enabled": False}})
```

Important: `JsonPatchFor["ServiceConfig", ...]` is intentionally rejected. Use
`Literal["ServiceConfig"]`.
