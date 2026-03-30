# Advanced Patterns

Use this page when baseline patch flows are already in place and you want
stricter contracts or richer behavior.

## Built-In RFC Generics

Built-in operations are generic, so you can narrow intent at the operation
boundary.

```python
from jsonpatchx import ReplaceOp
from jsonpatchx.types import JSONNumber

# Explicitly declare numeric replacement intent
op = ReplaceOp[JSONNumber](path="/quota", value=10)
```

This is useful when composing operations and you want pointer target types to
remain explicit.

## `JsonPatchRoute` for Assisted FastAPI Wiring

`JsonPatchRoute` is optional. Use it when you want stricter HTTP semantics and
reusable route metadata.

```python
from typing import Annotated

from jsonpatchx.fastapi import JsonPatchRoute

user_patch = JsonPatchRoute(
    UserPatch,
    strict_content_type=True,
    examples={
        "rename": {
            "summary": "Rename user",
            "value": [{"op": "replace", "path": "/name", "value": "Morgan"}],
        }
    },
)


@app.patch("/users/{user_id}", **user_patch.route_kwargs())
def patch_user(
    user_id: int,
    patch: Annotated[UserPatch, user_patch.Body()],
):
    ...
```

## Custom Pointer Backends (Current State)

Today, JsonPatchX supports custom `PointerBackend` implementations.

Use this when RFC 6901 JSON Pointer is not enough for your domain.

```python
from jsonpatchx import JSONPointer, JSONValue

class DotPointer(...):
    ...

# Operation bound to a custom pointer backend
path: JSONPointer[JSONValue, DotPointer]
```

If you define custom operations around custom pointer behavior, you own the
type-gating guarantees in your `apply()` logic.

For backend protocol details, see [Pointer Backends](pointer-backends.md).
