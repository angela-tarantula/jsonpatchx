"""
Best-effort baseline: discriminated unions + custom ops, still with caveats.

Known issues (intentional):
- Custom ops are not type-gated by pointer semantics.
- Swap validation is incomplete and does not prevent parent/child relationships.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator
from typing_extensions import Annotated

from examples._shared.app import install_error_handlers
from examples._shared.media import JSON_PATCH_MEDIA_TYPE
from examples._shared.store import get_config, save_config
from jsonpatch import apply_patch
from jsonpatch.exceptions import PatchError
from jsonpatch.types import JSONValue

from .pointer_utils import JsonPointerStr, resolve_pointer, set_pointer

app = FastAPI(
    title="Baseline demo (best-effort custom ops)",
    version="0.1.0",
    description=(
        "Best-effort baseline: discriminated unions plus manual custom ops dispatch."
    ),
)
install_error_handlers(app)


class _OpBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AddOp(_OpBase):
    op: Literal["add"] = "add"
    path: JsonPointerStr
    value: Any


class RemoveOp(_OpBase):
    op: Literal["remove"] = "remove"
    path: JsonPointerStr


class ReplaceOp(_OpBase):
    op: Literal["replace"] = "replace"
    path: JsonPointerStr
    value: Any


class MoveOp(_OpBase):
    op: Literal["move"] = "move"
    from_: JsonPointerStr = Field(alias="from")
    path: JsonPointerStr


class CopyOp(_OpBase):
    op: Literal["copy"] = "copy"
    from_: JsonPointerStr = Field(alias="from")
    path: JsonPointerStr


class TestOp(_OpBase):
    op: Literal["test"] = "test"
    path: JsonPointerStr
    value: Any


class IncrementOp(_OpBase):
    op: Literal["increment"] = "increment"
    path: JsonPointerStr
    value: int = Field(gt=0)


class AppendOp(_OpBase):
    op: Literal["append"] = "append"
    path: JsonPointerStr
    value: Any


class ExtendOp(_OpBase):
    op: Literal["extend"] = "extend"
    path: JsonPointerStr
    values: list[Any]


class ToggleOp(_OpBase):
    op: Literal["toggle"] = "toggle"
    path: JsonPointerStr


class SwapOp(_OpBase):
    op: Literal["swap"] = "swap"
    a: JsonPointerStr
    b: JsonPointerStr

    @model_validator(mode="after")
    def _only_prevent_same_path(self) -> "SwapOp":
        if self.a == self.b:
            raise ValueError("swap pointers must differ")
        return self


PatchOp = Annotated[
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
    | SwapOp,
    Field(discriminator="op"),
]


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
    description="Apply a JSON Patch document with manual custom ops.",
)
def patch_config(
    config_id: str,
    patch: JsonPatchBody = Body(
        ...,
        media_type=JSON_PATCH_MEDIA_TYPE,
        description="JSON Patch document (best-effort custom ops).",
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
            current = resolve_pointer(doc, op["path"])
            set_pointer(doc, op["path"], current + op["value"])
        elif op["op"] == "append":
            current = resolve_pointer(doc, op["path"])
            set_pointer(doc, op["path"], [*current, op["value"]])
        elif op["op"] == "extend":
            current = resolve_pointer(doc, op["path"])
            set_pointer(doc, op["path"], [*current, *op["values"]])
        elif op["op"] == "toggle":
            current = resolve_pointer(doc, op["path"])
            set_pointer(doc, op["path"], not current)
        elif op["op"] == "swap":
            value_a = resolve_pointer(doc, op["a"])
            value_b = resolve_pointer(doc, op["b"])
            set_pointer(doc, op["a"], value_b)
            set_pointer(doc, op["b"], value_a)
        else:
            raise HTTPException(status_code=400, detail=f"unknown op: {op['op']}")

    save_config(config_id, doc)
    return doc
