"""
Best-effort baseline: discriminated union models with manual pointer validation.
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, RootModel
from typing_extensions import Annotated

from examples._shared.app import install_error_handlers
from examples._shared.media import JSON_PATCH_MEDIA_TYPE
from examples._shared.store import get_config, save_config
from jsonpatch import apply_patch
from jsonpatch.exceptions import PatchError
from jsonpatch.types import JSONValue

from .pointer_utils import JsonPointerStr

app = FastAPI(
    title="Baseline demo (best-effort union)",
    version="0.1.0",
    description=(
        "Best-effort baseline: discriminated unions + manual pointer validation. Still misses "
        "registry-scoped pointer backends and typed pointer semantics."
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


PatchOp = Annotated[
    AddOp | RemoveOp | ReplaceOp | MoveOp | CopyOp | TestOp,
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
    description="Apply a JSON Patch document with discriminated union validation.",
)
def patch_config(
    config_id: str,
    patch: JsonPatchBody = Body(
        ...,
        media_type=JSON_PATCH_MEDIA_TYPE,
        description="JSON Patch document (best-effort schema).",
    ),
) -> JSONValue:
    doc = get_config(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")

    raw_ops: list[dict[str, JSONValue]] = [
        op.model_dump(by_alias=True) for op in patch.root
    ]

    try:
        updated = apply_patch(doc, raw_ops)
    except PatchError:
        raise

    save_config(config_id, updated)
    return updated
