import json
from pathlib import Path
from typing import Literal, override

import pytest
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
from jsonpatchx.registry import OperationRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONBoolean, JSONValue

SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "snapshots" / "openapi.json"


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
        return doc


LimitedRegistry = OperationRegistry[ToggleOp]
ExtendedRegistry = OperationRegistry[
    AddOp,
    CopyOp,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
    ToggleOp,
]
UserPatch = JsonPatchFor[User, LimitedRegistry]
MedicalPatch = JsonPatchFor[MedicalRecord, ExtendedRegistry]
JsonPatch = JsonPatchFor[Literal["Config"], ExtendedRegistry]
JsonPatchAlt = JsonPatchFor[Literal["Config"], ExtendedRegistry]
MedicalPatchAlt = JsonPatchFor[MedicalRecord, ExtendedRegistry]


def _build_openapi() -> dict[str, object]:
    app = FastAPI(
        title="jsonpatchx openapi snapshot",
        version="0.1.0",
        separate_input_output_schemas=False,
    )

    @app.patch("/users/{user_id}")
    def patch_user(user_id: int, patch: UserPatch = Body(...)) -> User:
        return User(id=user_id, name="ok")

    @app.patch("/records/{record_id}")
    def patch_record(record_id: int, patch: MedicalPatch = Body(...)) -> MedicalRecord:
        return MedicalRecord(id=record_id, diagnosis="ok")

    @app.patch("/configs/{config_id}")
    def patch_config(config_id: str, patch: JsonPatch = Body(...)) -> JSONValue:
        return {"ok": True}

    @app.patch("/configs/{config_id}/alt")
    def patch_config_alt(config_id: str, patch: JsonPatchAlt = Body(...)) -> JSONValue:
        return {"ok": True}

    @app.patch("/records/{record_id}/alt")
    def patch_record_alt(
        record_id: int, patch: MedicalPatchAlt = Body(...)
    ) -> MedicalRecord:
        return MedicalRecord(id=record_id, diagnosis="ok")

    return app.openapi()


def test_openapi_snapshot() -> None:
    if not SNAPSHOT_PATH.exists():  # pragma: no cover
        pytest.fail(f"OpenAPI snapshot missing: {SNAPSHOT_PATH}")

    expected = json.loads(SNAPSHOT_PATH.read_text())
    actual = _build_openapi()
    assert actual == expected
