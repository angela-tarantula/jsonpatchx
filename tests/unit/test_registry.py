import json
from typing import Any, Generic, Literal, cast, override

import pytest
from typing_extensions import TypeVar

from jsonpatchx.backend import _DEFAULT_POINTER_CLS
from jsonpatchx.exceptions import InvalidOperationRegistry, OperationNotRecognized
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.registry import GenericOperationRegistry, OperationRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch, StandardRegistry
from jsonpatchx.types import JSONValue
from tests.conftest import DotPointer


class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: str

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return doc


def test_registry_repr_and_hash() -> None:
    registry = OperationRegistry[ToggleOp]
    rep = repr(registry)
    assert "ToggleOp" in rep
    assert isinstance(hash(registry), int)


def test_jsonpatch_dunders_and_to_string() -> None:
    patch = JsonPatch(
        [
            {"op": "toggle", "path": "/a"},
            {"op": "toggle", "path": "/b"},
        ],
        registry=OperationRegistry[ToggleOp],
    )
    assert len(patch) == 2
    assert patch[0].op == "toggle"
    assert len(patch[:1]) == 1
    assert [op.op for op in patch] == ["toggle", "toggle"]

    payload = json.loads(patch.to_string())
    assert payload[0]["op"] == "toggle"


def test_parse_python_op_accepts_models_and_dicts() -> None:
    registry = OperationRegistry[ToggleOp]
    op_from_dict = registry.parse_python_op({"op": "toggle", "path": "/a"})
    assert isinstance(op_from_dict, ToggleOp)

    op_instance = ToggleOp(path="/b")
    op_from_model = registry.parse_python_op(op_instance)
    assert op_from_model is op_instance


def test_parse_python_op_rejects_other_registry_models() -> None:
    op_instance = StandardRegistry.parse_python_op(
        {"op": "add", "path": "/a", "value": 1}
    )
    registry = OperationRegistry[ToggleOp]
    with pytest.raises(OperationNotRecognized):
        registry.parse_python_op(op_instance)


def test_registry_rejects_missing_resolved_field_annotation() -> None:
    class CorruptedOp(OperationSchema):
        op: Literal["corrupted"] = "corrupted"
        path: JSONPointer[JSONValue]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    # Simulate runtime class mutation by external tooling/plugins: model_fields still has
    # "path", but get_type_hints() no longer resolves it from __annotations__.
    del CorruptedOp.__annotations__["path"]

    with pytest.raises(InvalidOperationRegistry, match="missing a resolved type"):
        OperationRegistry[CorruptedOp]


def test_registry_backend_rewrite_policies() -> None:
    class DotBackendA(DotPointer):
        pass

    class DotBackendB(DotPointer):
        pass

    P_backend = TypeVar("P_backend", bound=DotPointer, default=DotBackendA)

    class GenericOp(OperationSchema, Generic[P_backend]):
        op: Literal["generic-op"] = "generic-op"
        path: JSONPointer[JSONValue, P_backend]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    default_registry = OperationRegistry[GenericOp[DotBackendA]]
    default_op = cast(
        Any, default_registry.parse_python_op({"op": "generic-op", "path": "/a/b"})
    )
    assert isinstance(default_op.path.ptr, _DEFAULT_POINTER_CLS)

    custom_registry = GenericOperationRegistry[DotBackendB, GenericOp]
    custom_op = cast(
        Any, custom_registry.parse_python_op({"op": "generic-op", "path": "a.b"})
    )
    assert isinstance(custom_op.path.ptr, DotBackendB)
