"""
Demo 3: custom ops with an untyped JSON document.
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
from jsonpatchx import JSONValue, OperationRegistry, make_json_patch_body
from jsonpatchx.fastapi import patch_error_responses, patch_request_body

registry = OperationRegistry(
    IncrementOp,
    AppendOp,
    ExtendOp,
    ToggleBoolOp,
    SwapOp,
    EnsureObjectOp,
    RemoveNumberOp,
)
CustomPatch = make_json_patch_body(registry, name="Custom")

app = create_app(
    title="jsonpatch demo 3 (custom ops)",
    description="Custom ops become first-class: validation, OpenAPI, and dispatch.",
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
    responses=patch_error_responses(),
    openapi_extra=patch_request_body(
        "#/components/schemas/CustomPatch",
        examples={
            "increment-limit": {
                "summary": "limits: increment max_users",
                "value": [{"op": "increment", "path": "/max_users", "value": 10}],
            },
            "toggle-trial": {
                "summary": "limits: toggle trial",
                "value": [{"op": "toggle", "path": "/trial"}],
            },
            "ensure-flags": {
                "summary": "site: ensure /features is an object",
                "value": [{"op": "ensure_object", "path": "/features"}],
            },
            "append-tag": {
                "summary": "site: append a tag",
                "value": [{"op": "append", "path": "/tags", "value": "staff"}],
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
    patch: CustomPatch = Body(
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
