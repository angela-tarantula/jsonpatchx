"""
Demo 3: Non-pydantic JSON patching.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, HTTPException, Path

from examples.shared import (
    JSON_PATCH_MEDIA_TYPE,
    AppendOp,
    EnsureObjectOp,
    ExtendOp,
    IncrementOp,
    RemoveNumberOp,
    SwapOp,
    ToggleBoolOp,
    create_app,
    get_config,
    save_config,
)
from jsonpatchx import JSONValue, OperationRegistry, patch_body_for_json
from jsonpatchx.fastapi import patch_error_openapi_responses, patch_request_body

registry = OperationRegistry(
    IncrementOp,
    AppendOp,
    ExtendOp,
    ToggleBoolOp,
    SwapOp,
    EnsureObjectOp,
    RemoveNumberOp,
)
ConfigPatch = patch_body_for_json("Config", registry=registry)

app = create_app(
    title="Demo 3: Feature flags and limits",
    description="Non-pydantic JSON patching for config docs using `patch_body_for_json(...)`.",
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
    summary="Patch a config",
    description="Apply standard RFC 6902 ops plus custom ops to a config.",
    responses=patch_error_openapi_responses(),
    openapi_extra=patch_request_body(
        ConfigPatch,
        examples={
            "increment-limit": {
                "summary": "limits: increase max_users",
                "value": [{"op": "increment", "path": "/max_users", "value": 50}],
            },
            "toggle-trial": {
                "summary": "limits: toggle trial access",
                "value": [{"op": "toggle", "path": "/trial"}],
            },
            "ensure-flags": {
                "summary": "site: ensure /features is an object",
                "value": [{"op": "ensure_object", "path": "/features"}],
            },
            "append-tag": {
                "summary": "site: append a tag",
                "value": [{"op": "append", "path": "/tags", "value": "beta"}],
            },
            "swap": {
                "summary": "site: swap title and chat flag",
                "value": [{"op": "swap", "a": "/title", "b": "/features/chat"}],
            },
            "type-gated-remove": {
                "summary": "site: type-gated remove (expected failure)",
                "value": [{"op": "remove_number", "path": "/title"}],
            },
        },
    ),
)
def patch_config(
    config_id: str = Path(
        ...,
        description="Available configs: site, limits.",
        examples={"example": {"value": "site"}},
    ),
    patch: ConfigPatch = Body(
        ...,
        description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
        media_type=JSON_PATCH_MEDIA_TYPE,
    ),
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    updated = patch.apply(doc)
    save_config(config_id, updated)
    return updated
