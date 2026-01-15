"""
Demo 2: Custom registries bound to different Pydantic models using `JsonPatchFor[Model, CustomRegistry]`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Body, HTTPException, Path

from examples.fastapi.shared import (
    JSON_PATCH_MEDIA_TYPE,
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
from jsonpatchx.fastapi import patch_route_kwargs
from jsonpatchx.pydantic import JsonPatchFor

STRICT_JSON_PATCH = True

UserRegistry = OperationRegistry[StandardRegistry, IncrementOp, ToggleBoolOp]
TeamRegistry = OperationRegistry[StandardRegistry, AppendOp, IncrementOp]

UserPatch = JsonPatchFor[User, UserRegistry]
TeamPatch = JsonPatchFor[Team, TeamRegistry]

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
    **patch_route_kwargs(
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
        allow_application_json=not STRICT_JSON_PATCH,
    ),
)
def patch_user(
    user_id: Annotated[
        UserId,
        Path(...),
    ],
    patch: Annotated[
        UserPatch,
        Body(
            ...,
            media_type=JSON_PATCH_MEDIA_TYPE,
        ),
    ],
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
    **patch_route_kwargs(
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
        allow_application_json=not STRICT_JSON_PATCH,
    ),
)
def patch_team(
    team_id: Annotated[
        TeamId,
        Path(...),
    ],
    patch: Annotated[
        TeamPatch,
        Body(
            ...,
            media_type=JSON_PATCH_MEDIA_TYPE,
        ),
    ],
) -> Team:
    team = get_team(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="team not found")
    updated = patch.apply(team)
    save_team(team_id, updated)
    return updated
