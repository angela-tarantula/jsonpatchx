"""
Custom ops demo: model-aware patching with JsonPatchFor[(User, registry)].
"""

from __future__ import annotations

from fastapi import Body, HTTPException, Path

from examples._shared.app import create_app, patch_request_body
from examples._shared.media import JSON_PATCH_MEDIA_TYPE
from examples._shared.responses import patch_error_responses
from examples._shared.schemas import User
from examples._shared.store import get_user, save_user
from examples.custom_ops import AppendOp, IncrementOp, ToggleBoolOp
from jsonpatch import JsonPatchFor, OperationRegistry

registry = OperationRegistry.with_standard(IncrementOp, AppendOp, ToggleBoolOp)
UserPatch = JsonPatchFor[(User, registry)]

app = create_app(
    title="jsonpatch custom ops demo (typed model)",
    description="Patch a Pydantic model with custom ops registered in a registry.",
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
            "increment-quota": {
                "summary": "Increment user quota",
                "value": [{"op": "increment", "path": "/quota", "value": 1}],
            },
            "toggle-trial": {
                "summary": "Toggle trial",
                "value": [{"op": "toggle", "path": "/trial"}],
            },
            "append-tag": {
                "summary": "Append a tag",
                "value": [{"op": "append", "path": "/tags", "value": "staff"}],
            },
        },
    ),
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
