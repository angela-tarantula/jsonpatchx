"""
Demo 2: Custom registries bound to different Pydantic models using `patch_body_for_model(...)`.
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
from jsonpatchx import OperationRegistry, patch_body_for_model
from jsonpatchx.fastapi import patch_error_openapi_responses, patch_request_body

user_registry = OperationRegistry.with_standard(IncrementOp, ToggleBoolOp)
team_registry = OperationRegistry.with_standard(AppendOp, IncrementOp)

UserPatch = patch_body_for_model(User, registry=user_registry)
TeamPatch = patch_body_for_model(Team, registry=team_registry)

app = create_app(
    title="Demo 2: Billing and team ops",
    description="Custom registries for billing-style ops on users and teams using `patch_body_for_model(...)`.",
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
    responses=patch_error_openapi_responses(),
    openapi_extra=patch_request_body(
        UserPatch,
        examples={
            "increase-quota": {
                "summary": "Increase user quota",
                "value": [{"op": "increment", "path": "/quota", "value": 25}],
            },
            "toggle-trial": {
                "summary": "Toggle trial status",
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
    responses=patch_error_openapi_responses(),
    openapi_extra=patch_request_body(
        TeamPatch,
        examples={
            "append-tag": {
                "summary": "Append a team tag",
                "value": [{"op": "append", "path": "/tags", "value": "oncall"}],
            },
            "increment-max": {
                "summary": "Increase max_members",
                "value": [{"op": "increment", "path": "/max_members", "value": 3}],
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
