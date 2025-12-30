"""
Baseline custom ops demo — ad-hoc implementation.

Point of the file:
- Standard ops are easy and can be delegated to any JSON Patch engine (we use THIS project's).
- Custom ops require bespoke dispatch + semantics + (often) pointer parsing.

Run
  uvicorn examples.custom_ops_baseline:app --reload
"""

from __future__ import annotations

import copy
from collections.abc import MutableMapping
from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Path, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, RootModel, ValidationError
from jsonpatch import (
    apply_patch,  # any JsonPatch library works, but only for standard ops
)
from jsonpatch.exceptions import PatchError
from jsonpatch.types import JSONValue

JSON_PATCH_MEDIA_TYPE = "application/json-patch+json"

app = FastAPI(
    title="Baseline PATCH demo (custom ops are ad-hoc)",
    version="0.1.0",
    description=(
        "Baseline comparison: standard RFC 6902 ops can be delegated to a patch engine, "
        "but custom ops require a bespoke dispatcher and hand-rolled semantics."
    ),
)


@app.exception_handler(PatchError)
def patch_error_handler(request: Request, exc: PatchError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


# -------------------------
# Standard ops (baseline)
# -------------------------


class AddOp(BaseModel):
    op: Literal["add"] = "add"
    path: str
    value: Any


class RemoveOp(BaseModel):
    op: Literal["remove"] = "remove"
    path: str


class ReplaceOp(BaseModel):
    op: Literal["replace"] = "replace"
    path: str
    value: Any


class MoveOp(BaseModel):
    op: Literal["move"] = "move"
    from_: str = Field(alias="from")
    path: str


class CopyOp(BaseModel):
    op: Literal["copy"] = "copy"
    from_: str = Field(alias="from")
    path: str


class TestOp(BaseModel):
    op: Literal["test"] = "test"
    path: str
    value: Any


# -------------------------
# Custom ops (baseline)
# -------------------------


class IncrementOp(BaseModel):
    op: Literal["increment"] = "increment"
    path: str
    value: int = Field(gt=0)


class AppendOp(BaseModel):
    op: Literal["append"] = "append"
    path: str
    value: Any


class ExtendOp(BaseModel):
    op: Literal["extend"] = "extend"
    path: str
    values: list[Any]


class ToggleOp(BaseModel):
    op: Literal["toggle"] = "toggle"
    path: str


class SwapOp(BaseModel):
    op: Literal["swap"] = "swap"
    a: str
    b: str


PatchOp = (
    AddOp
    | RemoveOp
    | ReplaceOp
    | MoveOp
    | CopyOp
    | TestOp
    | IncrementOp
    | AppendOp
    | ExtendOp
    | ToggleOp
    | SwapOp
)


class JsonPatchBody(RootModel[list[PatchOp]]):
    pass


_CONFIGS: MutableMapping[str, JSONValue] = {
    "site": {"title": "Example", "features": {"chat": True}, "tags": ["admin"]},
    "limits": {"max_users": 5, "trial": False},
}


# -------------------------
# Minimal JSON Pointer helper (baseline has to reinvent)
# -------------------------


def _tokens(ptr: str) -> list[str]:
    if ptr == "":
        return []
    if not ptr.startswith("/"):
        raise HTTPException(status_code=400, detail=f"Invalid JSON Pointer: {ptr!r}")
    tokens = ptr.split("/")[1:]
    return [t.replace("~1", "/").replace("~0", "~") for t in tokens]


def _get(doc: Any, ptr: str) -> Any:
    cur = doc
    for tok in _tokens(ptr):
        if isinstance(cur, dict):
            if tok not in cur:
                raise HTTPException(status_code=400, detail=f"Path not found: {ptr!r}")
            cur = cur[tok]
        elif isinstance(cur, list):
            if tok == "-" or not tok.isdigit():
                raise HTTPException(
                    status_code=400, detail=f"Invalid array index in {ptr!r}"
                )
            i = int(tok)
            if i < 0 or i >= len(cur):
                raise HTTPException(
                    status_code=400, detail=f"Index out of range in {ptr!r}"
                )
            cur = cur[i]
        else:
            raise HTTPException(status_code=400, detail=f"Non-container at {ptr!r}")
    return cur


def _set(doc: Any, ptr: str, value: Any) -> Any:
    toks = _tokens(ptr)
    if not toks:
        return value  # root set

    cur = doc
    for tok in toks[:-1]:
        if isinstance(cur, dict):
            if tok not in cur:
                raise HTTPException(status_code=400, detail=f"Path not found: {ptr!r}")
            cur = cur[tok]
        elif isinstance(cur, list):
            if tok == "-" or not tok.isdigit():
                raise HTTPException(
                    status_code=400, detail=f"Invalid array index in {ptr!r}"
                )
            i = int(tok)
            if i < 0 or i >= len(cur):
                raise HTTPException(
                    status_code=400, detail=f"Index out of range in {ptr!r}"
                )
            cur = cur[i]
        else:
            raise HTTPException(status_code=400, detail=f"Non-container at {ptr!r}")

    last = toks[-1]
    if isinstance(cur, dict):
        cur[last] = value
        return doc
    if isinstance(cur, list):
        if last == "-":
            cur.append(value)
            return doc
        if not last.isdigit():
            raise HTTPException(
                status_code=400, detail=f"Invalid array index in {ptr!r}"
            )
        i = int(last)
        if i < 0 or i > len(cur):
            raise HTTPException(
                status_code=400, detail=f"Index out of range in {ptr!r}"
            )
        if i == len(cur):
            cur.append(value)
        else:
            cur[i] = value
        return doc

    raise HTTPException(status_code=400, detail=f"Non-container at {ptr!r}")


@app.get("/configs/{config_id}", response_model=Any, tags=["configs"])
def get_config(
    config_id: str = Path(
        ...,
        description="Available configs: site, limits.",
        example="site",
    ),
) -> JSONValue:
    doc = _CONFIGS.get(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    return doc


@app.patch(
    "/configs/{config_id}",
    response_model=Any,
    tags=["configs"],
    summary="Patch a config",
    description="Apply standard RFC 6902 ops plus custom ops to a config.",
    responses={
        400: {
            "description": "Patch application error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                        "required": ["detail"],
                    }
                }
            },
        }
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                JSON_PATCH_MEDIA_TYPE: {
                    "schema": {"$ref": "#/components/schemas/JsonPatchBody"},
                    "examples": {
                        "increment-limit": {
                            "summary": "limits: increment max_users",
                            "value": [
                                {
                                    "op": "increment",
                                    "path": "/max_users",
                                    "value": 2,
                                }
                            ],
                        },
                        "toggle-flag": {
                            "summary": "limits: toggle trial",
                            "value": [{"op": "toggle", "path": "/trial"}],
                        },
                        "append-tag": {
                            "summary": "site: append to tags",
                            "value": [
                                {"op": "append", "path": "/tags", "value": "staff"}
                            ],
                        },
                        "swap": {
                            "summary": "site: swap title and chat flag",
                            "value": [
                                {"op": "swap", "a": "/title", "b": "/features/chat"}
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
    patch: JsonPatchBody = Body(
        ...,
        media_type=JSON_PATCH_MEDIA_TYPE,
        description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
    ),
) -> JSONValue:
    doc = _CONFIGS.get(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")

    # Keep the baseline transactional for the demo.
    working: Any = copy.deepcopy(doc)

    standard_ops: list[dict[str, Any]] = []

    for op in patch.root:
        if isinstance(op, IncrementOp):
            cur = _get(working, op.path)
            if not isinstance(cur, int):
                raise HTTPException(
                    status_code=400, detail=f"increment expects int at {op.path!r}"
                )
            working = _set(working, op.path, cur + op.value)

        elif isinstance(op, ToggleOp):
            cur = _get(working, op.path)
            if not isinstance(cur, bool):
                raise HTTPException(
                    status_code=400, detail=f"toggle expects bool at {op.path!r}"
                )
            working = _set(working, op.path, (not cur))

        elif isinstance(op, AppendOp):
            cur = _get(working, op.path)
            if not isinstance(cur, list):
                raise HTTPException(
                    status_code=400, detail=f"append expects list at {op.path!r}"
                )
            working = _set(working, op.path, [*cur, op.value])

        elif isinstance(op, ExtendOp):
            cur = _get(working, op.path)
            if not isinstance(cur, list):
                raise HTTPException(
                    status_code=400, detail=f"extend expects list at {op.path!r}"
                )
            working = _set(working, op.path, [*cur, *op.values])

        elif isinstance(op, SwapOp):
            va = _get(working, op.a)
            vb = _get(working, op.b)
            working = _set(working, op.a, vb)
            working = _set(working, op.b, va)

        else:
            standard_ops.append(op.model_dump(by_alias=True))

    if standard_ops:
        working = apply_patch(working, standard_ops, inplace=True)

    _CONFIGS[config_id] = working
    return working


@app.get("/health", tags=["meta"])
def health(response: Response) -> dict[str, Any]:
    response.headers["cache-control"] = "no-store"
    return {"status": "ok"}
