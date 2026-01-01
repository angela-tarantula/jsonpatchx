"""
Standard API demo: typed model patching with JsonPatchFor[User].

Highlights
- JsonPatchFor produces a typed JSON Patch request body with strong OpenAPI.
- Typed pointer semantics show up as runtime behavior.
- Optional strict Content-Type enforcement via a dependency.
"""

from __future__ import annotations

from fastapi import Body, HTTPException, Path

from examples._shared.app import (
    create_app,
    patch_content_type_dependency,
    patch_request_body,
)
from examples._shared.media import JSON_PATCH_MEDIA_TYPE
from examples._shared.responses import patch_error_responses
from examples._shared.schemas import User
from examples._shared.store import get_user, save_user
from jsonpatch import JsonPatchFor

STRICT_JSON_PATCH = False

UserPatch = JsonPatchFor[User]

app = create_app(
    title="jsonpatch standard demo (typed model)",
    description=("Patch a Pydantic model with JsonPatchFor[User]."),
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
    user_id: int,
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
