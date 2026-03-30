"""
OpenAPI contract-focused demo app for schema generation and model-reuse invariants.

This app is used by snapshot tests to lock down JsonPatchFor schema behavior for:
- distinct target/registry combinations, and
- deterministic schema reuse for identical target/registry pairs.
"""

from __future__ import annotations

from typing import Literal, override

from fastapi import Body, FastAPI
from pydantic import BaseModel, ConfigDict

from jsonpatchx import (
    AddOp,
    CopyOp,
    JsonPatchFor,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONBoolean, JSONValue


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


class MedicalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    diagnosis: str


class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return doc  # pragma: no cover


type LimitedRegistry = ToggleOp
type ExtendedRegistry = (
    AddOp | CopyOp | MoveOp | RemoveOp | ReplaceOp | TestOp | ToggleOp
)
UserPatch = JsonPatchFor[User, LimitedRegistry]
MedicalPatch = JsonPatchFor[MedicalRecord, ExtendedRegistry]
JsonPatch = JsonPatchFor[Literal["Config"], ExtendedRegistry]
JsonPatchAlt = JsonPatchFor[Literal["Config"], ExtendedRegistry]
MedicalPatchAlt = JsonPatchFor[MedicalRecord, ExtendedRegistry]

app = FastAPI(
    title="JsonPatchX openapi snapshot",
    version="0.1.0",
    separate_input_output_schemas=False,
)


@app.patch("/users/{user_id}")
def patch_user(user_id: int, patch: UserPatch = Body(...)) -> User:
    return User(id=user_id, name="ok")  # pragma: no cover


@app.patch("/records/{record_id}")
def patch_record(record_id: int, patch: MedicalPatch = Body(...)) -> MedicalRecord:
    return MedicalRecord(id=record_id, diagnosis="ok")  # pragma: no cover


@app.patch("/configs/{config_id}")
def patch_config(config_id: str, patch: JsonPatch = Body(...)) -> JSONValue:
    return {"ok": True}  # pragma: no cover


@app.patch("/configs/{config_id}/alt")
def patch_config_alt(config_id: str, patch: JsonPatchAlt = Body(...)) -> JSONValue:
    return {"ok": True}  # pragma: no cover


@app.patch("/records/{record_id}/alt")
def patch_record_alt(
    record_id: int, patch: MedicalPatchAlt = Body(...)
) -> MedicalRecord:
    return MedicalRecord(id=record_id, diagnosis="ok")  # pragma: no cover
