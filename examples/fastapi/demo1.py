"""
Demo 1: Standard JSON Patch with Pydantic models using JsonPatchFor[Model, StandardRegistry].
"""

from __future__ import annotations

from typing import Annotated

from fastapi import HTTPException, Path

from examples.fastapi.shared import User, UserId, create_app, get_user, save_user
from jsonpatchx import StandardRegistry
from jsonpatchx.fastapi import JsonPatchRoute
from jsonpatchx.pydantic import JsonPatchFor

STRICT_JSON_PATCH = True

UserPatch = JsonPatchFor[User, StandardRegistry]
user_patch = JsonPatchRoute(
    UserPatch,
    examples={
        "rename-customer": {
            "summary": "Rename the customer",
            "value": [{"op": "replace", "path": "/name", "value": "Avery"}],
        },
        "add-segment": {
            "summary": "Add a segment tag",
            "value": [{"op": "add", "path": "/tags/-", "value": "enterprise"}],
        },
    },
    strict_content_type=STRICT_JSON_PATCH,
)

app = create_app(
    title="Demo 1: Customer profile patching",
    description="Standard JSON Patch on customer profiles using `JsonPatchFor[Model, StandardRegistry]`.",
)


@app.get(
    "/users/{user_id}",
    response_model=User,
    tags=["users"],
    summary="Get a user",
    description="Fetch a user by id.",
)
def get_user_endpoint(
    user_id: Annotated[
        UserId,
        Path(...),
    ],
) -> User:
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.patch(
    "/users/{user_id}",
    response_model=User,
    tags=["users"],
    summary="Patch a user",
    description="Apply a JSON Patch document to a User model.",
    **user_patch.route_kwargs(),
)
def patch_user(
    user_id: Annotated[
        UserId,
        Path(...),
    ],
    patch: Annotated[UserPatch, user_patch.Body()],
) -> User:
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
