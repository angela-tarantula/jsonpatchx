"""
Standard API demo: typed ops against untyped JSONValue documents.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, HTTPException, Path

from examples._shared.app import create_app, patch_request_body
from examples._shared.media import JSON_PATCH_MEDIA_TYPE
from examples._shared.responses import patch_error_responses
from examples._shared.store import get_config, save_config
from jsonpatch import OperationRegistry, make_json_patch_body
from jsonpatch.types import JSONValue

StandardPatch = make_json_patch_body(OperationRegistry.standard(), name="Standard")

app = create_app(
    title="jsonpatch standard demo (untyped doc)",
    description=(
        "Apply typed RFC 6902 operations to plain JSONValue documents with "
        "make_json_patch_body(...)."
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
    description="Apply a JSON Patch document to a JSONValue config.",
    responses=patch_error_responses(),
    openapi_extra=patch_request_body(
        "#/components/schemas/StandardPatch",
        examples={
            "insert-first": {
                "summary": "Insert the first feature",
                "value": [{"op": "add", "path": "/features/list/0", "value": "first"}],
            }
        },
    ),
)
def patch_config(
    config_id: str,
    patch: StandardPatch = Body(
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
