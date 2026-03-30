# Getting Started

This page gets you to a working RFC 6902 flow quickly, then shows how to apply
the same PATCH model as a typed FastAPI contract.

## Install

```sh
pip install jsonpatchx
```

## Example 1: Standards-Compliant Runtime Patching

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

## Example 2: FastAPI PATCH Contract

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from jsonpatchx import JsonPatchFor


class User(BaseModel):
    id: int
    email: str
    active: bool


app = FastAPI()

@app.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: int, patch: JsonPatchFor[User]) -> User:
    user = load_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
```

See this endpoint live: [Interactive PATCH preview](example.com)

> Demo note: This preview validates PATCH payloads and returns patched JSON, but
> does not persist changes.

## What This Gives You

- RFC 6902-compatible patch behavior for runtime document updates.
- A typed FastAPI request contract for PATCH endpoints.
- A flexible path from standard JSON Patch to custom PATCH contracts.

## Next Steps

The examples above show baseline RFC behavior. The next layer is extension.

1. Define custom operations as strongly-typed Pydantic models.
2. Use typed pointers to make operation intent explicit and harden operation
   targeting.
3. Use JSONPath selectors for expressive, query-style targeting when a single
   pointer is not enough.
4. Control which operations are allowed on each endpoint.
5. Optionally load operation sets from declarative configuration and gate
   rollout with feature flags.
6. Evolve contracts by extending schemas, adding operations, and deprecating
   obsolete fields or operations.
