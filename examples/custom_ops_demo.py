"""
FastAPI + jsonpatch (this library) — Custom ops demo.

Assumes:
  examples/custom_ops.py
contains IncrementOp / AppendOp / ExtendOp / ToggleBoolOp / SwapOp.

Run
  uvicorn examples.custom_ops_demo:app --reload
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Response

from examples.custom_ops import AppendOp, ExtendOp, IncrementOp, SwapOp, ToggleBoolOp
from jsonpatch import OperationRegistry, make_json_patch_body
from jsonpatch.types import JSONValue

JSON_PATCH_MEDIA_TYPE = "application/json-patch+json"

registry = OperationRegistry.standard().with_standard(
    IncrementOp, AppendOp, ExtendOp, ToggleBoolOp, SwapOp
)
ConfigPatchWithCustomOps = make_json_patch_body(registry)

app = FastAPI(
    title="jsonpatch OpenAPI demo (custom ops)",
    version="0.1.0",
    description=(
        "Demonstrates registry-registered custom operations that become first-class in "
        "validation and OpenAPI generation."
    ),
)

_CONFIGS: MutableMapping[str, JSONValue] = {
    "site": {"title": "Example", "features": {"chat": True}, "tags": ["admin"]},
    "limits": {"max_users": 5, "trial": False},
}


@app.get("/configs/{config_id}", response_model=Any, tags=["configs"])
def get_config(config_id: str) -> JSONValue:
    doc = _CONFIGS.get(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    return doc


@app.patch(
    "/configs/{config_id}",
    response_model=Any,
    tags=["configs"],
    summary="Patch a config (standard + custom ops)",
    description=(
        "Custom ops are registered in the OperationRegistry, so they appear in the same "
        "discriminated union as RFC 6902 operations."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                JSON_PATCH_MEDIA_TYPE: {
                    "schema": {"$ref": "#/components/schemas/JsonPatchBody"},
                    "examples": {
                        "increment-limit": {
                            "summary": "Custom: increment a number",
                            "value": [
                                {
                                    "op": "increment",
                                    "path": "/limits/max_users",
                                    "value": 2,
                                }
                            ],
                        },
                        "toggle-flag": {
                            "summary": "Custom: toggle a boolean",
                            "value": [{"op": "toggle", "path": "/site/features/chat"}],
                        },
                        "append-tag": {
                            "summary": "Custom: append to a list",
                            "value": [
                                {"op": "append", "path": "/site/tags", "value": "staff"}
                            ],
                        },
                        "swap": {
                            "summary": "Custom: swap two locations",
                            "value": [
                                {"op": "swap", "a": "/site/title", "b": "/limits/trial"}
                            ],
                        },
                    },
                },
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/JsonPatchBody"}
                },
            },
        }
    },
)
def patch_config(
    config_id: str,
    patch: ConfigPatchWithCustomOps = Body(
        ...,
        media_type=JSON_PATCH_MEDIA_TYPE,
        description=(
            "RFC 6902 JSON Patch document with registry-registered custom operations. "
            "Prefer Content-Type: application/json-patch+json."
        ),
    ),
) -> JSONValue:
    doc = _CONFIGS.get(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    updated = patch.apply(doc)
    _CONFIGS[config_id] = updated
    return updated


@app.get("/health", tags=["meta"])
def health(response: Response) -> dict[str, Any]:
    response.headers["cache-control"] = "no-store"
    return {"status": "ok"}
