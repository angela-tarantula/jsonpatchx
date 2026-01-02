"""
Custom pointer backend demo: dot-separated pointers.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, HTTPException, Path

from examples._shared.app import create_app, patch_request_body
from examples._shared.media import JSON_PATCH_MEDIA_TYPE
from examples._shared.responses import patch_error_responses
from examples._shared.store import get_config, save_config
from examples.pointer_backends.simple_backend import DotPointer
from jsonpatch import OperationRegistry, make_json_patch_body
from jsonpatch.types import JSONValue

registry = OperationRegistry.with_standard(pointer_cls=DotPointer)
DotPointerPatch = make_json_patch_body(registry, name="DotPointer")

app = create_app(
    title="jsonpatch pointer backend demo",
    description=(
        "Registry-scoped pointer backends change parsing semantics without changing ops."
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
    summary="Patch a config (dot pointers)",
    description="Use dot-separated pointers like 'features.chat'.",
    responses=patch_error_responses(),
    openapi_extra=patch_request_body(
        "#/components/schemas/DotPointer",
        examples={
            "dot-pointer": {
                "summary": "site: replace chat flag",
                "value": [{"op": "replace", "path": "features.chat", "value": False}],
            }
        },
    ),
)
def patch_config(
    config_id: str,
    patch: DotPointerPatch = Body(
        ...,
        description="JSON Patch document with dot-separated pointers.",
        media_type=JSON_PATCH_MEDIA_TYPE,
    ),
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    updated = patch.apply(doc)
    save_config(config_id, updated)
    return updated
