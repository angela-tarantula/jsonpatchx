"""
Average baseline: list[dict[str, Any]] request body with minimal validation.
"""

from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException, Path

from examples._shared.app import install_error_handlers
from examples._shared.media import JSON_PATCH_MEDIA_TYPE
from examples._shared.store import get_config, save_config
from jsonpatch import apply_patch
from jsonpatch.exceptions import PatchError
from jsonpatch.types import JSONValue

app = FastAPI(
    title="Baseline demo (loose schema)",
    version="0.1.0",
    description=(
        "Baseline comparison: the request body is a list of dicts with minimal validation."
    ),
)
install_error_handlers(app)


def _validate_patch(raw_patch: list[dict[str, Any]]) -> None:
    for idx, op in enumerate(raw_patch):
        if not isinstance(op, dict):
            raise HTTPException(status_code=400, detail=f"op[{idx}] must be an object")
        if "op" not in op or "path" not in op:
            raise HTTPException(
                status_code=400, detail=f"op[{idx}] must include 'op' and 'path'"
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
    description="Apply a JSON Patch document with minimal validation.",
)
def patch_config(
    config_id: str,
    patch: list[dict[str, Any]] = Body(
        ...,
        description="JSON Patch document (loosely validated).",
        media_type=JSON_PATCH_MEDIA_TYPE,
    ),
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")

    _validate_patch(patch)

    try:
        updated = apply_patch(doc, patch)
    except PatchError:
        raise
    save_config(config_id, updated)
    return updated
