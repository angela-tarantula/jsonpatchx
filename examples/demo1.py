"""
Demo 1: standard model patching with JsonPatchFor[User].
"""

from __future__ import annotations

from fastapi import Body, HTTPException, Path

from examples.shared import JSON_PATCH_MEDIA_TYPE, User, create_app, get_user, save_user
from jsonpatchx import JsonPatchFor
from jsonpatchx.fastapi import (
    patch_content_type_dependency,
    patch_error_responses,
    patch_request_body,
)

STRICT_JSON_PATCH = True

UserPatch = JsonPatchFor[User]

app = create_app(
    title="jsonpatch demo 1 (typed model)",
    description="Patch a Pydantic model with JsonPatchFor[User].",
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
    responses=patch_error_responses(),
    openapi_extra=patch_request_body(
        "#/components/schemas/UserPatch",
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
