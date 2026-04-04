# Getting Started

This page gets you to a working patch flow in two steps:

1. apply a plain RFC 6902 patch document;
2. use the same operation set as a typed FastAPI request contract.

## Install

```sh
pip install jsonpatchx
pip install "jsonpatchx[fastapi]"
```

Install the extra only if you want the FastAPI helpers.

## 1. Apply a plain RFC 6902 patch

```python
from jsonpatchx import JsonPatch

doc = {"name": "Ada", "roles": ["engineer"]}

patch = JsonPatch(
    [
        {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
        {"op": "add", "path": "/roles/-", "value": "maintainer"},
    ]
)

updated = patch.apply(doc)
```

This is ordinary JSON Patch. No custom operations, no FastAPI integration, no
new semantics.

`JsonPatch` defaults to the standard RFC 6902 registry, so the input document
above is parsed and validated as plain JSON Patch. By default, `apply()` works
against a copy of the input document.

Already have a JSON string? `JsonPatch.from_string(text)` parses and validates
it with the same default RFC registry.

## 2. Turn the same RFC ops into a FastAPI contract

```python
from typing import Annotated

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from jsonpatchx import JsonPatchFor, StandardRegistry
from jsonpatchx.fastapi import JsonPatchRoute, install_jsonpatch_error_handlers


class User(BaseModel):
    id: int
    email: str
    active: bool


UserPatch = JsonPatchFor[User, StandardRegistry]
user_patch_route = JsonPatchRoute(UserPatch)

app = FastAPI()
install_jsonpatch_error_handlers(app)


@app.patch(
    "/users/{user_id}",
    response_model=User,
    **user_patch_route.route_kwargs(),
)
def patch_user(
    user_id: int,
    patch: Annotated[UserPatch, user_patch_route.Body()],
) -> User:
    user = load_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
```

A matching request still looks like standard JSON Patch:

```http
PATCH /users/1
Content-Type: application/json-patch+json

[
  {"op": "replace", "path": "/email", "value": "ada@example.com"},
  {"op": "replace", "path": "/active", "value": false}
]
```

## What changed between the two examples

The operation vocabulary did not change. The second example still accepts
standard RFC 6902 operations through `StandardRegistry`.

What changed is the contract around them:

- the request body is now a named patch model
- the allowed operations are explicit at the route boundary
- request parsing and OpenAPI come from the same source
- `patch.apply(user)` revalidates the patched result as `User`

That is the core JsonPatchX move: keep JSON Patch where it works, then add
contract semantics where APIs need them.

## Where to go next

The next page explains `JsonPatchFor[Target, Registry]` in more detail and shows
why it is useful even before you define a single custom operation.
