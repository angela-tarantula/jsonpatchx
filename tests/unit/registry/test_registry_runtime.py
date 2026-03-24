import json
from typing import Generic, Literal, cast, override

import pytest
from pytest import Subtests
from typing_extensions import TypeVar

from jsonpatchx.exceptions import OperationNotRecognized
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.registry import StandardRegistry, _RegistrySpec
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONValue
from tests.support.pointer_backends import DotPointer


class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: str

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return doc


def test_registry_spec_parse_happy_path(subtests: Subtests) -> None:
    class IncrementOp(OperationSchema):
        op: Literal["increment"] = "increment"
        path: str
        value: int = 1

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class ToggleByPathOp(OperationSchema):
        op: Literal["toggle-by-path"] = "toggle-by-path"
        path: str

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    registry = _RegistrySpec.from_typeform(IncrementOp | ToggleByPathOp)

    with subtests.test("parse_op succeeds"):
        op = registry.parse_python_op({"op": "increment", "path": "/foo", "value": 3})
        assert isinstance(op, IncrementOp)
        assert op.path == "/foo"
        assert op.value == 3

    with subtests.test("parse_patch succeeds"):
        patch = registry.parse_python_patch(
            [
                {"op": "increment", "path": "/foo", "value": 1},
                {"op": "toggle-by-path", "path": "/foo"},
            ]
        )
        op1, op2 = patch
        assert isinstance(op1, IncrementOp)
        assert isinstance(op2, ToggleByPathOp)


def test_registry_spec_preserves_explicit_pointer_backend() -> None:
    class DotRemoveOp(OperationSchema):
        op: Literal["dot-remove"] = "dot-remove"
        path: JSONPointer[JSONValue, DotPointer]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    op = DotRemoveOp.model_validate({"path": "a.b"})
    assert isinstance(op.path.ptr, DotPointer)

    registry = _RegistrySpec.from_typeform(DotRemoveOp)
    parsed = cast(
        DotRemoveOp,
        registry.parse_python_op({"op": "dot-remove", "path": "a.b"}),
    )
    assert isinstance(parsed.path.ptr, DotPointer)


def test_jsonpatch_dunders_and_to_string() -> None:
    patch = JsonPatch(
        [
            {"op": "toggle", "path": "/a"},
            {"op": "toggle", "path": "/b"},
        ],
        registry=ToggleOp,
    )
    assert len(patch) == 2
    assert patch[0] == ToggleOp(path="/a")
    assert len(patch[:1]) == 1
    assert [op for op in patch] == [ToggleOp(path="/a"), ToggleOp(path="/b")]

    payload = json.loads(patch.to_string())
    assert payload == [
        {"op": "toggle", "path": "/a"},
        {"op": "toggle", "path": "/b"},
    ]


def test_parse_python_op_accepts_models_and_dicts() -> None:
    registry = _RegistrySpec.from_typeform(ToggleOp)
    op_from_dict = registry.parse_python_op({"op": "toggle", "path": "/a"})
    assert op_from_dict == ToggleOp(path="/a")

    op_instance = ToggleOp(path="/b")
    op_from_model = registry.parse_python_op(op_instance)
    assert op_from_model is op_instance


def test_parse_python_op_rejects_other_registry_models() -> None:
    standard = _RegistrySpec.from_typeform(StandardRegistry)
    op_instance = standard.parse_python_op({"op": "add", "path": "/a", "value": 1})

    registry = _RegistrySpec.from_typeform(ToggleOp)
    with pytest.raises(OperationNotRecognized):
        registry.parse_python_op(op_instance)


def test_parse_python_patch_rejects_other_registry_model_instances() -> None:
    standard = _RegistrySpec.from_typeform(StandardRegistry)
    op_instance = standard.parse_python_op({"op": "add", "path": "/a", "value": 1})

    registry = _RegistrySpec.from_typeform(ToggleOp)
    with pytest.raises(OperationNotRecognized):
        registry.parse_python_patch([op_instance])


def test_parse_json_op_validates_single_json_operation() -> None:
    registry = _RegistrySpec.from_typeform(ToggleOp)

    op = registry.parse_json_op(b'{"op":"toggle","path":"/a"}')
    assert op == ToggleOp(path="/a")


def test_registry_supports_mixed_pointer_backends() -> None:
    class SlashOp(OperationSchema):
        op: Literal["slash-op"] = "slash-op"
        path: JSONPointer[JSONValue]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class DotOp(OperationSchema):
        op: Literal["dot-op"] = "dot-op"
        path: JSONPointer[JSONValue, DotPointer]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    registry = _RegistrySpec.from_typeform(SlashOp | DotOp)

    slash = registry.parse_python_op({"op": "slash-op", "path": "/a/b"})
    dot = registry.parse_python_op({"op": "dot-op", "path": "a.b"})

    assert slash == SlashOp(path="/a/b")
    assert dot == DotOp(path="a.b")


def test_registry_model_input_requires_exact_class_identity(subtests: Subtests) -> None:
    class Backend1(DotPointer):
        pass

    class Backend2(DotPointer):
        pass

    P_backend = TypeVar("P_backend", bound=DotPointer, default=Backend1)

    class GenericOp(OperationSchema, Generic[P_backend]):
        op: Literal["identity-op"] = "identity-op"
        path: JSONPointer[JSONValue, P_backend]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class SubGenericOp(GenericOp[Backend1]):
        pass

    registry = _RegistrySpec.from_typeform(GenericOp[Backend1])

    accepted = GenericOp[Backend1].model_validate({"path": "a.b"})
    parsed = registry.parse_python_op(accepted)
    assert parsed is accepted

    with subtests.test("generic specialization mismatch is rejected"):
        wrong_backend_specialization = GenericOp[Backend2].model_validate(
            {"path": "a.b"}
        )
        with pytest.raises(OperationNotRecognized):
            registry.parse_python_op(wrong_backend_specialization)

    with subtests.test("subclass instance mismatch is rejected"):
        subclass_instance = SubGenericOp.model_validate({"path": "a.b"})
        with pytest.raises(OperationNotRecognized):
            registry.parse_python_op(subclass_instance)
