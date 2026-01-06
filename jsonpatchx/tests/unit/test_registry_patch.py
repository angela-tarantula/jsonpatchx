import json
from typing import Literal, override

from jsonpatchx.registry import OperationRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONValue


class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: str

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return doc


def test_registry_repr_and_hash() -> None:
    registry = OperationRegistry(ToggleOp)
    rep = repr(registry)
    assert "OperationRegistry" in rep
    assert "ToggleOp" in rep
    assert isinstance(hash(registry), int)


def test_jsonpatch_dunders_and_to_string() -> None:
    patch = JsonPatch(
        [
            {"op": "toggle", "path": "/a"},
            {"op": "toggle", "path": "/b"},
        ],
        registry=OperationRegistry(ToggleOp),
    )
    assert len(patch) == 2
    assert patch[0].op == "toggle"
    assert len(patch[:1]) == 1
    assert [op.op for op in patch] == ["toggle", "toggle"]

    payload = json.loads(patch.to_string())
    assert payload[0]["op"] == "toggle"
