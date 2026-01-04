"""
Demo 2: custom ops bound to Pydantic models.
"""

from __future__ import annotations

from fastapi import Body, HTTPException, Path

from examples.shared import (
    JSON_PATCH_MEDIA_TYPE,
    AppendOp,
    IncrementOp,
    Team,
    ToggleBoolOp,
    User,
    create_app,
    get_team,
    get_user,
    save_team,
    save_user,
)
from jsonpatchx import JsonPatchFor, OperationRegistry
from jsonpatchx.fastapi import patch_error_responses, patch_request_body

user_registry = OperationRegistry.with_standard(IncrementOp, ToggleBoolOp)
team_registry = OperationRegistry.with_standard(AppendOp, IncrementOp)

UserPatch = JsonPatchFor[User, user_registry]
TeamPatch = JsonPatchFor[Team, team_registry]

app = create_app(
    title="jsonpatch demo 2 (model + custom ops)",
    description="Custom registries bound to Pydantic models.",
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
    description="Apply custom ops to a User model.",
    responses=patch_error_responses(),
    openapi_extra=patch_request_body(
        "#/components/schemas/UserPatch",
        examples={
            "increment-quota": {
                "summary": "Increment user quota",
                "value": [{"op": "increment", "path": "/quota", "value": 10}],
            },
            "toggle-trial": {
                "summary": "Toggle trial",
                "value": [{"op": "toggle", "path": "/trial"}],
            },
        },
    ),
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


@app.get(
    "/teams/{team_id}",
    response_model=Team,
    tags=["teams"],
    summary="Get a team",
    description="Fetch a team by id.",
)
def get_team_endpoint(
    team_id: int = Path(
        ...,
        description="Available teams: 1, 2.",
        examples={"example": {"value": 1}},
    ),
) -> Team:
    team = get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="team not found")
    return team


@app.patch(
    "/teams/{team_id}",
    response_model=Team,
    tags=["teams"],
    summary="Patch a team",
    description="Apply custom ops to a Team model.",
    responses=patch_error_responses(),
    openapi_extra=patch_request_body(
        "#/components/schemas/TeamPatch",
        examples={
            "append-tag": {
                "summary": "Append a tag",
                "value": [{"op": "append", "path": "/tags", "value": "infra"}],
            },
            "increment-max": {
                "summary": "Increment max_members",
                "value": [{"op": "increment", "path": "/max_members", "value": 5}],
            },
        },
    ),
)
def patch_team(
    team_id: int = Path(
        ...,
        description="Available teams: 1, 2.",
        examples={"example": {"value": 1}},
    ),
    patch: TeamPatch = Body(
        ...,
        description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
        media_type=JSON_PATCH_MEDIA_TYPE,
    ),
) -> Team:
    team = get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="team not found")
    updated = patch.apply(team)
    save_team(team_id, updated)
    return updated
