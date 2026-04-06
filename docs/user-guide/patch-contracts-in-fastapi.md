# PATCH Contracts in FastAPI

`JsonPatch` is for patch documents.

`JsonPatchFor[...]` is for route contracts.

That distinction is the center of JsonPatchX.

## `JsonPatchFor[Target]` is the default route-facing form

The friendly form is:

```python
UserPatch = JsonPatchFor[User]
```

That is the type you want most of the time when a FastAPI route accepts standard
JSON Patch against a `User`.

The explicit form is there when the route's mutation vocabulary needs to be part
of the contract too:

```python
PublicUserPatch = JsonPatchFor[User, PublicUserOps]
```

That second type argument is not the opening move. It is the policy-aware form
you reach for when different routes, clients, or environments should not all
accept the same operations.

## You Can Also Use `Literal["SchemaName"]`

Most routes should use a model target:

```python
UserPatch = JsonPatchFor[User]
```

If your endpoint patches raw JSON (not a concrete Pydantic model),
`JsonPatchFor` also supports a string-literal target:

```python
from typing import Literal

ConfigPatch = JsonPatchFor[Literal["ServiceConfig"]]
```

This gives you a stable, readable OpenAPI schema name for the PATCH contract
without introducing a dedicated target model class.

## A route can stay simple and still be explicit

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr
from jsonpatchx import JsonPatchFor

class TeamSettings(BaseModel):
    display_name: str
    seat_limit: int
    billing_email: EmailStr

app = FastAPI()

@app.patch("/teams/{team_id}/settings", response_model=TeamSettings)
def patch_team_settings(
    team_id: int,
    patch: JsonPatchFor[TeamSettings],
) -> TeamSettings:
    settings = load_team_settings(team_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="team not found")

    updated = patch.apply(settings)
    save_team_settings(team_id, updated)
    return updated
```

That route is still plain RFC 6902.

What changed is not the payload shape. What changed is that the route has an
explicit patch model instead of a generic JSON list.

## What gets validated, and when

When a route accepts `JsonPatchFor[User]`, there are several checks happening in
sequence.

First, the request body has to parse as a patch document made of known
operations.

Second, each operation validates its own fields before mutation runs. Invalid
paths, missing required fields, wrong value shapes, and custom-op invariants
fail here.

Third, the patch is applied in order.

Fourth, the patched result is validated as the target model.

That fourth step matters. A patch can be syntactically valid and still produce a
resource that violates the route’s schema. JsonPatchX treats that as part of the
contract.

## Why this is better than `list[dict]`

A bare `list[dict]` body is easy to accept and hard to govern.

It leaves too much unsaid:

- which operations are actually supported
- whether the patched result is revalidated
- whether OpenAPI matches runtime behavior
- whether the route is meant to stay standard or evolve later
- how one endpoint is supposed to differ from another

`JsonPatchFor[...]` makes that contract explicit without inventing a new patch
format.

## The optional FastAPI helper layer

`JsonPatchFor[...]` is enough by itself.

For public routes, the helper layer is usually worth adding. It gives you
content-type enforcement, consistent error mapping, and per-route customization
such as operation examples.

```python
from typing import Annotated
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, EmailStr

from jsonpatchx import JsonPatchFor
from jsonpatchx.fastapi import JsonPatchRoute, install_jsonpatch_error_handlers

class User(BaseModel):
    id: int
    email: EmailStr
    active: bool

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

That is the recommended shape when you want the route to enforce
`application/json-patch+json` and publish a more polished PATCH contract in
OpenAPI.

## Where the next decision starts

Once the route contract is explicit, the next question is usually not “how do I
write a custom operation?”

It is “should every client be allowed to send every operation this route could
understand?”

That is the job of registries.
