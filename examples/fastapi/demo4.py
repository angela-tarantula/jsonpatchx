"""
Demo 4: registry-scoped pointer backend with FastAPI dependency injection.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Body, Depends, HTTPException, Path

from examples.fastapi.shared import (
    JSON_PATCH_MEDIA_TYPE,
    ConfigId,
    DotPointer,
    User,
    UserId,
    create_app,
    get_config,
    get_user,
    save_config,
    save_user,
)
from jsonpatchx import GenericOperationRegistry, JSONValue, StandardRegistry
from jsonpatchx.fastapi import PatchDependency, patch_route_kwargs
from jsonpatchx.pydantic import JsonPatchFor

STRICT_JSON_PATCH = True

app = create_app(
    title="Demo 4: Dot-pointer settings",
    description=(
        "Registry-scoped dot-pointer backends for config and user settings. "
        "Uses `PatchDependency(...)` with explicit request body configuration."
    ),
)

registry = GenericOperationRegistry[StandardRegistry, DotPointer]
DotPointerPatch = JsonPatchFor[Literal["Config"], registry]
UserPatch = JsonPatchFor[User, registry]


@app.get(
    "/configs/{config_id}",
    response_model=JSONValue,
    tags=["configs"],
    summary="Get a config",
    description="Fetch a config by id.",
)
def get_config_endpoint(
    config_id: Annotated[
        ConfigId,
        Path(
            ...,
        ),
    ],
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    return doc


@app.patch(
    "/configs/{config_id}",
    response_model=JSONValue,
    tags=["configs"],
    summary="Patch a config (dot pointers)",
    description="Use dot-separated pointers like 'features.chat'.",
    **patch_route_kwargs(allow_application_json=not STRICT_JSON_PATCH),
)
def patch_config(
    config_id: Annotated[
        ConfigId,
        Path(
            ...,
        ),
    ],
    patch: Annotated[
        DotPointerPatch,
        Depends(
            PatchDependency(
                DotPointerPatch,
                request_param=Body(
                    ...,
                    description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
                    media_type=JSON_PATCH_MEDIA_TYPE,
                    openapi_examples={
                        "dot-pointer": {
                            "summary": "site: replace chat flag",
                            "value": [
                                {
                                    "op": "replace",
                                    "path": "features.chat",
                                    "value": False,
                                }
                            ],
                        }
                    },
                ),
            )
        ),
    ],
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
    user_id: Annotated[
        UserId,
        Path(
            ...,
        ),
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
    summary="Patch a user (dot pointers)",
    description="Use dot-separated pointers like 'quota' or 'tags.0'.",
    **patch_route_kwargs(allow_application_json=not STRICT_JSON_PATCH),
)
def patch_user(
    user_id: Annotated[
        UserId,
        Path(
            ...,
        ),
    ],
    patch: Annotated[
        UserPatch,
        Depends(
            PatchDependency(
                UserPatch,
                request_param=Body(
                    ...,
                    description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
                    media_type=JSON_PATCH_MEDIA_TYPE,
                    openapi_examples={
                        "set-quota": {
                            "summary": "set user quota",
                            "value": [{"op": "replace", "path": "quota", "value": 300}],
                        }
                    },
                ),
            )
        ),
    ],
) -> User:
    user = get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
