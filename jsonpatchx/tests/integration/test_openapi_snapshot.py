import json
from pathlib import Path
from typing import Literal, override

import pytest

pytest.importorskip("fastapi")
from fastapi import Body, Depends, FastAPI
from pydantic import BaseModel, ConfigDict

from jsonpatchx import JsonPatchFor
from jsonpatchx.fastapi import (
    patch_body_for_json_with_dep,
    patch_body_for_model_with_dep,
)
from jsonpatchx.registry import OperationRegistry, StandardRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONBoolean, JSONPointer, JSONValue

SNAPSHOT_PATH = Path(__file__).resolve().parents[1] / "snapshots" / "openapi.json"


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return doc


def _build_openapi() -> dict[str, object]:
    app = FastAPI(title="jsonpatchx openapi snapshot", version="0.1.0")

    ToggleRegistry = OperationRegistry[ToggleOp]
    UserPatch = JsonPatchFor[User, StandardRegistry]
    CustomUserPatch = JsonPatchFor[User, ToggleRegistry]
    JsonPatch = JsonPatchFor["Config", ToggleRegistry]

    JsonPatchWithDep, JsonDepends, json_openapi = patch_body_for_json_with_dep(
        "DotConfigPatch", registry=ToggleRegistry, app=app
    )
    ModelPatchWithDep, ModelDepends, model_openapi = patch_body_for_model_with_dep(
        User, registry=ToggleRegistry, app=app
    )

    @app.patch("/users/{user_id}")
    def patch_user(user_id: int, patch: UserPatch = Body(...)) -> User:
        return User(id=user_id, name="ok")

    @app.patch("/users/{user_id}/custom")
    def patch_user_custom(user_id: int, patch: CustomUserPatch = Body(...)) -> User:
        return User(id=user_id, name="ok")

    @app.patch("/configs/{config_id}")
    def patch_config(config_id: str, patch: JsonPatch = Body(...)) -> JSONValue:
        return {"ok": True}

    @app.patch("/configs/{config_id}/dep", openapi_extra=json_openapi)
    def patch_config_dep(
        config_id: str, patch: JsonPatchWithDep = Depends(JsonDepends)
    ) -> JSONValue:
        return {"ok": True}

    @app.patch("/users/{user_id}/dep", openapi_extra=model_openapi)
    def patch_user_dep(
        user_id: int, patch: ModelPatchWithDep = Depends(ModelDepends)
    ) -> User:
        return User(id=user_id, name="ok")

    return app.openapi()


def test_openapi_snapshot() -> None:
    if not SNAPSHOT_PATH.exists():
        pytest.fail(f"OpenAPI snapshot missing: {SNAPSHOT_PATH}")

    expected = json.loads(SNAPSHOT_PATH.read_text())
    actual = _build_openapi()
    assert actual == expected
