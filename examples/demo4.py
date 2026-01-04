"""
Demo 4: registry-scoped pointer backend with FastAPI dependency injection.
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Path

from examples.shared import (
    JSON_PATCH_MEDIA_TYPE,
    DotPointer,
    create_app,
    get_config,
    save_config,
)
from jsonpatchx import JSONValue, OperationRegistry
from jsonpatchx.fastapi import make_json_patch_body_with_dep, patch_error_responses

app = create_app(
    title="jsonpatch demo 4 (pointer backends)",
    description=(
        "Registry-scoped pointer backends change parsing semantics without changing ops."
    ),
)

registry = OperationRegistry.with_standard(pointer_cls=DotPointer)
DotPointerPatch, DotPointerPatchDepends, openapi_extra = make_json_patch_body_with_dep(
    registry,
    name="DotPointer",
    media_type=JSON_PATCH_MEDIA_TYPE,
    app=app,
    examples={
        "dot-pointer": {
            "summary": "site: replace chat flag",
            "value": [{"op": "replace", "path": "features.chat", "value": False}],
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
    responses=patch_error_responses(),
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
