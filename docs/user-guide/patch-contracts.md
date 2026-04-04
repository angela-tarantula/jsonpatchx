# PATCH Contracts in FastAPI

`JsonPatch` parses a patch document.

`JsonPatchFor[Target, Registry]` turns patch documents into an API contract.

That distinction is the center of JsonPatchX.

## The two type arguments are the contract

`Target` says what the patch applies to.

`Registry` says which operations the route accepts.

Start with the standard RFC 6902 registry:

```python
from typing import Literal

from jsonpatchx import JsonPatchFor, StandardRegistry

UserPatch = JsonPatchFor[User, StandardRegistry]
TenantConfigPatch = JsonPatchFor[Literal["TenantConfig"], StandardRegistry]
```

Use a Pydantic model target when the patched result should be revalidated as
that model.

Use `Literal["SchemaName"]` when the route patches raw JSON but you still want
stable, human-readable OpenAPI component names.

## A complete contract-bound route

```python
from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, EmailStr

from jsonpatchx import JsonPatchFor, StandardRegistry
from jsonpatchx.fastapi import JsonPatchRoute, install_jsonpatch_error_handlers


class TeamSettings(BaseModel):
    display_name: str
    seat_limit: int
    billing_email: EmailStr


TeamSettingsPatch = JsonPatchFor[TeamSettings, StandardRegistry]
team_settings_patch_route = JsonPatchRoute(TeamSettingsPatch)

app = FastAPI()
install_jsonpatch_error_handlers(app)


@app.patch(
    "/teams/{team_id}/settings",
    response_model=TeamSettings,
    **team_settings_patch_route.route_kwargs(),
)
def patch_team_settings(
    team_id: int,
    patch: Annotated[TeamSettingsPatch, team_settings_patch_route.Body()],
) -> TeamSettings:
    settings = load_team_settings(team_id)
    updated = patch.apply(settings)
    save_team_settings(team_id, updated)
    return updated
```

There are no custom operations here. This route is still plain RFC 6902.

The difference is that the route now has an explicit patch contract instead of a
bare JSON list.

## What gets validated, and when

A `JsonPatchFor[...]` model gives you a specific validation sequence:

1. the request body must parse as a patch document made of operations from the
   declared registry;
2. each operation model validates its own fields before mutation happens;
3. `patch.apply(target)` runs the operations against the supplied target;
4. if the target is a Pydantic model, the patched result is revalidated as that
   model.

That fourth step matters. A patch can be syntactically valid and still produce a
result that violates your resource schema. JsonPatchX treats that as part of the
PATCH contract, not an afterthought.

## Why this is better than `list[dict]`

Accepting `list[dict]` makes PATCH bodies easy to receive and hard to govern.

Using `JsonPatchFor[Target, Registry]` gives you:

- a named request model instead of an anonymous payload
- a precise operation union instead of “some dicts with an `op` field”
- target-model revalidation as part of patch application
- OpenAPI that matches the route’s real mutation vocabulary

That is useful even if you never go beyond the RFC operations.

## Start with `StandardRegistry`

This is the easiest way to adopt JsonPatchX in an existing API:

```python
UserPatch = JsonPatchFor[User, StandardRegistry]
```

That single line says something your old route probably did not say clearly
enough:

“This endpoint accepts standard JSON Patch, and only standard JSON Patch,
against this target.”

Custom operations come later, when your domain starts repeating the same
mutation patterns and you want the payload to say what the caller actually
means.
