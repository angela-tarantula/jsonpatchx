"""
Custom ops demo: registry-driven parsing and typed pointer semantics.
"""

from __future__ import annotations

from typing import Any, Literal, override

from fastapi import Body, HTTPException, Path

from examples._shared.app import create_app, patch_request_body
from examples._shared.media import JSON_PATCH_MEDIA_TYPE
from examples._shared.responses import patch_error_responses
from examples._shared.store import get_config, save_config
from examples.custom_ops import (
    AppendOp,
    EnsureObjectOp,
    ExtendOp,
    IncrementOp,
    SwapOp,
    ToggleBoolOp,
)
from jsonpatch import OperationRegistry, RemoveOp, make_json_patch_body
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONNumber, JSONPointer, JSONValue


class RemoveNumberOp(OperationSchema):
    op: Literal["remove_number"] = "remove_number"
    path: JSONPointer[JSONNumber]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return RemoveOp(path=self.path).apply(doc)


registry = OperationRegistry.with_standard(
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
    title="jsonpatch custom ops demo",
    description=(
        "Custom ops become first-class: validation, OpenAPI, dispatch, and pointer typing."
    ),
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
                "value": [{"op": "increment", "path": "/max_users", "value": 2}],
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
                "summary": "demo: type-gated remove (expected failure)",
                "value": [{"op": "remove_number", "path": "/title"}],
            },
            "swap-same": {
                "summary": "demo: unexpected exception wrapping",
                "value": [{"op": "swap", "a": "/title", "b": "/title"}],
            },
        },
    ),
)
def patch_config(
    config_id: str,
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
