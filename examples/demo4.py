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
from jsonpatchx.fastapi import (
    patch_body_for_json_with_dep,
    patch_error_openapi_responses,
)

app = create_app(
    title="Demo 4: Custom JSON Pointer implementations",
    description=(
        "Registry-scoped pointer backends change parsing semantics without changing operation schemas. Requires `patch_body_for_json_with_dep`."
    ),
)

registry = OperationRegistry.with_standard(pointer_cls=DotPointer)
DotPointerPatch, DotPointerPatchDepends, openapi_extra = patch_body_for_json_with_dep(
    "DotPointer",
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
