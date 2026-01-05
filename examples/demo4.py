"""
Demo 4: registry-scoped pointer backend with FastAPI dependency injection.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Path

from examples.shared import (
    JSON_PATCH_MEDIA_TYPE,
    DotPointer,
    User,
    create_app,
    get_config,
    get_user,
    save_config,
    save_user,
)
from jsonpatchx import JSONValue, OperationRegistry
from jsonpatchx.fastapi import (
    patch_body_for_json_with_dep,
    patch_body_for_model_with_dep,
    patch_error_openapi_responses,
)

app = create_app(
    title="Demo 4: Dot-pointer settings",
    description=(
        "Registry-scoped dot-pointer backends for config and user settings. "
        "Uses `patch_body_for_json_with_dep(...)` and `patch_body_for_model_with_dep(...)`."
    ),
)

registry = OperationRegistry.with_standard(pointer_cls=DotPointer)
DotPointerPatch, DotPointerPatchDepends, openapi_extra = patch_body_for_json_with_dep(
    "Config",
    registry=registry,
    media_type=JSON_PATCH_MEDIA_TYPE,
    app=app,
    examples={
        "dot-pointer": {
            "summary": "site: replace chat flag",
            "value": [{"op": "replace", "path": "features.chat", "value": False}],
        }
    },
)
UserPatch, UserPatchDepends, user_openapi_extra = patch_body_for_model_with_dep(
    User,
    registry=registry,
    media_type=JSON_PATCH_MEDIA_TYPE,
    app=app,
    examples={
        "set-quota": {
            "summary": "set user quota",
            "value": [{"op": "replace", "path": "quota", "value": 300}],
        }
    },
)


@app.get(
    "/configs/{config_id}",
    response_model=Any,
    tags=["configs"],
    summary="Get a config",
    description="Fetch a config by id.",
)
def get_config_endpoint(
    config_id: str = Path(
        ...,
        description="Available configs: site, limits.",
        examples={"example": {"value": "site"}},
    ),
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    return doc


@app.patch(
    "/configs/{config_id}",
    response_model=Any,
    tags=["configs"],
    summary="Patch a config (dot pointers)",
    description="Use dot-separated pointers like 'features.chat'.",
    responses=patch_error_openapi_responses(),
    openapi_extra=openapi_extra,
)
def patch_config(
    config_id: str = Path(
        ...,
        description="Available configs: site, limits.",
        examples={"example": {"value": "site"}},
    ),
    patch: DotPointerPatch = Depends(DotPointerPatchDepends),
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    updated = patch.apply(doc)
    save_config(config_id, updated)
    return updated


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
    summary="Patch a user (dot pointers)",
    description="Use dot-separated pointers like 'quota' or 'tags.0'.",
    responses=patch_error_openapi_responses(),
    openapi_extra=user_openapi_extra,
)
def patch_user(
    user_id: int = Path(
        ...,
        description="Available users: 1, 2.",
        examples={"example": {"value": 1}},
    ),
    patch: UserPatch = Depends(UserPatchDepends),
) -> User:
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
