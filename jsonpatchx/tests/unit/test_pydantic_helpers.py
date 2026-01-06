from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

from jsonpatchx.pydantic import JsonPatchFor, patch_body_for_json, patch_body_for_model
from jsonpatchx.registry import OperationRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONPointer, JSONValue


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


def test_jsonpatchfor_requires_basemodel_type() -> None:
    with pytest.raises(TypeError):
        JsonPatchFor[int]  # type: ignore[misc]


def test_patch_body_for_model_registry_type() -> None:
    with pytest.raises(TypeError):
        patch_body_for_model(User, registry="nope")  # type: ignore[arg-type]


def test_patch_body_for_json_schema_name_validation() -> None:
    with pytest.raises(ValueError):
        patch_body_for_json("bad name!")


def test_patch_body_for_json_naming() -> None:
    PatchBody = patch_body_for_json("Config")
    assert PatchBody.__name__ == "ConfigPatchDocument"


def test_jsonpatchfor_empty_patch_returns_same_instance() -> None:
    UserPatch = JsonPatchFor[User]
    patch = UserPatch.model_validate([])
    user = User(id=1, name="Ada")
    assert patch.apply(user) is user


def test_jsonpatchfor_with_custom_registry() -> None:
    class EchoOp(OperationSchema):
        op: Literal["echo"] = "echo"
        path: JSONPointer[JSONValue]
        value: JSONValue

        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    registry = OperationRegistry.with_standard(EchoOp)
    PatchBody = patch_body_for_model(User, registry=registry)
    patch = PatchBody.model_validate([{"op": "echo", "path": "/name", "value": "ok"}])
    assert patch.ops
