from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.registry import OperationRegistry, StandardRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONPointer, JSONValue


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


def test_jsonpatchfor_requires_basemodel_type() -> None:
    with pytest.raises(TypeError):
        JsonPatchFor[int, StandardRegistry]  # type: ignore[misc]


def test_jsonpatchfor_requires_model_type() -> None:
    with pytest.raises(TypeError):
        JsonPatchFor[int, StandardRegistry]  # type: ignore[misc]

    with pytest.raises(TypeError):
        JsonPatchFor["Config", int]  # type: ignore[misc]


def test_jsonpatchfor_with_custom_registry() -> None:
    class EchoOp(OperationSchema):
        op: Literal["echo"] = "echo"
        path: JSONPointer[JSONValue]
        value: JSONValue

        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    Registry = OperationRegistry[EchoOp]
    PatchBody = JsonPatchFor[User, Registry]
    patch = PatchBody.model_validate([{"op": "echo", "path": "/name", "value": "ok"}])
    assert patch.ops
