# Getting Started

Read this guide in order. It starts with plain
[RFC 6902](https://datatracker.ietf.org/doc/html/rfc6902) patching and builds
from there.

## Install

```sh
pip install jsonpatchx
```

For FastAPI integrations:

```sh
pip install jsonpatchx[fastapi]
```

## Apply a Plain RFC 6902 Patch

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

## Turn RFC 6902 Into a FastAPI Contract

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
- document-dependent checks happen during `patch.apply(...)`
- the patched result is validated as `User`

It also gives your FastAPI route a real PATCH request schema in OpenAPI/Swagger
instead of undocumented patch dicts.

> Most routes should use a Pydantic model target. If you are patching raw JSON,
> you can still define a PATCH contract by giving it a name instead of a schema,
> for example: `JsonPatchFor[Literal["DeploymentSpec"]]`.

## Optional: FastAPI Helpers

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

<!--
See it for yourself: [Interactive PATCH Demo](https://example.com)
-->

## You Can Stop Here for Server-Side RFC 6902

If all you need is to accept and apply standard RFC 6902 patch documents on the
server, you can stop here.

If you also want to build a Python patch client, see
[Patch Clients](patch-clients.md).

The rest of the guide focuses on richer PATCH contracts such as custom
operations, route-specific registries, and contract evolution.
