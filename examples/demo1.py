"""
Demo 1: Standard JSON Patch with Pydantic models using JsonPatchFor[Model].
"""

from __future__ import annotations

from fastapi import Body, HTTPException, Path

from examples.shared import JSON_PATCH_MEDIA_TYPE, User, create_app, get_user, save_user
from jsonpatchx import JsonPatchFor
from jsonpatchx.fastapi import (
    patch_content_type_dependency,
    patch_error_openapi_responses,
    patch_request_body,
)

STRICT_JSON_PATCH = True

UserPatch = JsonPatchFor[User]

app = create_app(
    title="Demo 1: Standard JSON Patch",
    description="Standard JSON Patch with Pydantic models using `JsonPatchFor[Model]`.",
)


@app.get(
    "/users/{user_id}",
    response_model=User,
    tags=["users"],
    summary="Get a user",
    description="Fetch a user by id.",
)
def get_user_endpoint(
    user_id: int = Path(
        ...,
        description="Available users: 1, 2.",
        examples={"example": {"value": 1}},
    ),
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
    responses=patch_error_openapi_responses(),
    openapi_extra=patch_request_body(
        UserPatch,
        examples={
            "rename-user": {
                "summary": "Replace the user's name",
                "value": [{"op": "replace", "path": "/name", "value": "Morgan"}],
            },
            "append-tag": {
                "summary": "Append a tag",
                "value": [{"op": "add", "path": "/tags/-", "value": "staff"}],
            },
        },
    ),
    dependencies=patch_content_type_dependency(STRICT_JSON_PATCH),
)
def patch_user(
    user_id: int = Path(
        ...,
        description="Available users: 1, 2.",
        examples={"example": {"value": 1}},
    ),
    patch: UserPatch = Body(
        ...,
        description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
        media_type=JSON_PATCH_MEDIA_TYPE,
    ),
) -> User:
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
