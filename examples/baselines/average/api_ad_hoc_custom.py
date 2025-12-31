"""
Average baseline: ad-hoc custom ops with hand-rolled pointer logic.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Path
from pydantic import BaseModel, Field, RootModel

from examples._shared.app import install_error_handlers
from examples._shared.media import JSON_PATCH_MEDIA_TYPE
from examples._shared.store import get_config, save_config
from jsonpatch import apply_patch
from jsonpatch.exceptions import PatchError
from jsonpatch.types import JSONValue

from .pointer_utils import get_value, set_value

app = FastAPI(
    title="Baseline demo (custom ops are ad-hoc)",
    version="0.1.0",
    description=(
        "Baseline comparison: standard ops can be delegated to a patch engine, but custom ops "
        "require bespoke dispatch and pointer handling."
    ),
)
install_error_handlers(app)


# Standard ops (loose baseline)


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


# Custom ops (ad-hoc)


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
)
def patch_config(
    config_id: str,
    patch: JsonPatchBody = Body(
        ...,
        media_type=JSON_PATCH_MEDIA_TYPE,
        description="JSON Patch document (custom ops are ad-hoc).",
    ),
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")

    raw_ops = [op.model_dump(by_alias=True) for op in patch.root]

    for op in raw_ops:
        if op["op"] in {"add", "remove", "replace", "move", "copy", "test"}:
            try:
                doc = apply_patch(doc, [op], inplace=True)
            except PatchError:
                raise
            continue

        if op["op"] == "increment":
            current = get_value(doc, op["path"])
            set_value(doc, op["path"], current + op["value"])
        elif op["op"] == "append":
            current = get_value(doc, op["path"])
            set_value(doc, op["path"], [*current, op["value"]])
        elif op["op"] == "extend":
            current = get_value(doc, op["path"])
            set_value(doc, op["path"], [*current, *op["values"]])
        elif op["op"] == "toggle":
            current = get_value(doc, op["path"])
            set_value(doc, op["path"], not current)
        elif op["op"] == "swap":
            value_a = get_value(doc, op["a"])
            value_b = get_value(doc, op["b"])
            set_value(doc, op["a"], value_b)
            set_value(doc, op["b"], value_a)
        else:
            raise HTTPException(status_code=400, detail=f"unknown op: {op['op']}")

    save_config(config_id, doc)
    return doc
