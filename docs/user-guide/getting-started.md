# Getting Started

This page gets you from plain RFC 6902 patching to a real FastAPI PATCH contract
with the fewest moving parts.

## Install

> JsonPatchX is not on PyPI yet. Install it from a local clone instead:

<!--
```sh
pip install jsonpatchx
```
-->

```sh
git clone https://github.com/angela-tarantula/jsonpatchx.git
cd jsonpatchx
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Optional FastAPI helpers come later:

<!--
```sh
pip install "jsonpatchx[fastapi]"
```
-->

```sh
pip install -e ".[fastapi]"
```

You do not need that extra just to use `JsonPatch` or `JsonPatchFor[...]`.

## 1. Apply a plain RFC 6902 patch

```python
from jsonpatchx import JsonPatch

doc = {
    "name": "Ada",
    "roles": ["engineer"],
    "active": True,
}

patch = JsonPatch(
    [
        {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
        {"op": "add", "path": "/roles/-", "value": "maintainer"},
    ]
)

updated = patch.apply(doc)
```

That is ordinary JSON Patch.

`JsonPatch` is Pydantic-backed, so the patch document is parsed and validated
before it is applied. If you already have JSON text, use
`JsonPatch.from_string(...)` and apply it the same way.

## 2. Turn the RFC into a FastAPI contract

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

from jsonpatchx import JsonPatchFor


class User(BaseModel):
    id: int
    email: EmailStr
    active: bool


app = FastAPI()


@app.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: int, patch: JsonPatchFor[User]) -> User:
    user = load_user(user_id)
    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
```

The request body on the wire is still standard JSON Patch:

```http
PATCH /users/1
Content-Type: application/json-patch+json

[
  {"op": "replace", "path": "/email", "value": "ada@example.com"},
  {"op": "replace", "path": "/active", "value": false}
]
```

What changed is the contract around it.

`JsonPatchFor[User]` means:

- the request body is parsed as a patch document, not a bare `list[dict]`
- the operations are validated before mutation
- the patched result is validated as `User`
- the route gets a real PATCH request schema instead of undocumented patch dicts

That is the smallest useful JsonPatchX route.

> Most routes should use a Pydantic model target. If you are patching raw JSON,
> `JsonPatchFor` also supports string-literal targets:
> `JsonPatchFor[Literal["DeploymentSpec"]]`.

## 3. Optional FastAPI Helpers

You can opt into enforcing `application/json-patch+json` and installing the
recommended HTTP error mapping:

```python
from typing import Annotated
from fastapi import FastAPI, HTTPException

from jsonpatchx import JsonPatchFor
from jsonpatchx.fastapi import JsonPatchRoute, install_jsonpatch_error_handlers

UserPatch = JsonPatchFor[User]
user_patch_route = JsonPatchRoute(
    UserPatch,
    operation_examples=[
        {
            "summary": "Deactivate a user",
            "value": [
                {"op": "replace", "path": "/active", "value": False},
            ],
        }
    ],
)

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

See it for yourself: [Interactive PATCH Demo](https://example.com)

## You Don’t Have to Buy Into the Whole Vision

If all you want is RFC 6902, you can stop here.
