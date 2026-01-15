"""
Demo 2: Custom registries bound to different Pydantic models using `JsonPatchFor[Model, CustomRegistry]`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import HTTPException, Path

from examples.fastapi.shared import (
    AppendOp,
    IncrementOp,
    Team,
    TeamId,
    ToggleBoolOp,
    User,
    UserId,
    create_app,
    get_team,
    get_user,
    save_team,
    save_user,
)
from jsonpatchx import OperationRegistry, StandardRegistry
from jsonpatchx.fastapi import JsonPatchRoute
from jsonpatchx.pydantic import JsonPatchFor

STRICT_JSON_PATCH = True

UserRegistry = OperationRegistry[StandardRegistry, IncrementOp, ToggleBoolOp]
TeamRegistry = OperationRegistry[StandardRegistry, AppendOp, IncrementOp]

UserPatch = JsonPatchFor[User, UserRegistry]
TeamPatch = JsonPatchFor[Team, TeamRegistry]
user_patch = JsonPatchRoute(
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
    strict_content_type=STRICT_JSON_PATCH,
)
team_patch = JsonPatchRoute(
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
    strict_content_type=STRICT_JSON_PATCH,
)

app = create_app(
    title="Demo 2: Billing and team ops",
    description="Custom registries for billing-style ops on users and teams using `JsonPatchFor[Model, CustomRegistry]`.",
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
    description="Apply custom ops to a User model.",
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


@app.get(
    "/teams/{team_id}",
    response_model=Team,
    tags=["teams"],
    summary="Get a team",
    description="Fetch a team by id.",
)
def get_team_endpoint(
    team_id: Annotated[
        TeamId,
        Path(...),
    ],
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
    **team_patch.route_kwargs(),
)
def patch_team(
    team_id: Annotated[
        TeamId,
        Path(...),
    ],
    patch: Annotated[TeamPatch, team_patch.Body()],
) -> Team:
    team = get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="team not found")
    updated = patch.apply(team)
    save_team(team_id, updated)
    return updated
