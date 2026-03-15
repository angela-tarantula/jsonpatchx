import json
from abc import abstractmethod
from typing import Any, Generic, Literal, cast, override

import pytest
from pytest import Subtests
from typing_extensions import TypeVar

from jsonpatchx.exceptions import InvalidOperationRegistry, OperationNotRecognized
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.registry import StandardRegistry, _RegistrySpec
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONValue
from tests.conftest import DotPointer


class ToggleOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: str

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return doc


def test_invalid_registry_typeforms(subtests: Subtests) -> None:
    class FirstOp(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class SecondOp(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class AbstractOp(OperationSchema):
        op: Literal["abstract"] = "abstract"

        @abstractmethod
        def apply(self, doc: JSONValue) -> JSONValue:
            raise NotImplementedError

    with subtests.test("duplicate op literals are rejected"):
        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(FirstOp | SecondOp)

    with subtests.test("non-OperationSchema inputs are rejected"):
        with pytest.raises(
            InvalidOperationRegistry,
            match="registry must be a union of concrete OperationSchemas",
        ):
            _RegistrySpec.from_typeform(cast(Any, str))

        with pytest.raises(
            InvalidOperationRegistry,
            match="registry must be a union of concrete OperationSchemas",
        ):
            _RegistrySpec.from_typeform(cast(Any, 42))

    with subtests.test("OperationSchema base class is rejected"):
        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(OperationSchema)

    with subtests.test("abstract operation classes are rejected"):
        with pytest.raises(InvalidOperationRegistry):
            _RegistrySpec.from_typeform(AbstractOp)


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


def test_registry_spec_repr_hash_equality_are_set_based() -> None:
    class FirstOp(OperationSchema):
        op: Literal["cache-first"] = "cache-first"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class SecondOp(OperationSchema):
        op: Literal["cache-second"] = "cache-second"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    registry_a = _RegistrySpec.from_typeform(FirstOp | SecondOp)
    registry_b = _RegistrySpec.from_typeform(SecondOp | FirstOp)

    assert registry_a == registry_b
    assert hash(registry_a) == hash(registry_b)


def test_registry_spec_model_for_and_unknown_rejection() -> None:
    registry = _RegistrySpec.from_typeform(ToggleOp)
    assert registry.model_for("toggle") is ToggleOp
    with pytest.raises(OperationNotRecognized):
        registry.model_for("not-allowed")


def test_jsonpatch_dunders_and_to_string() -> None:
    patch = JsonPatch(
        [
            {"op": "toggle", "path": "/a"},
            {"op": "toggle", "path": "/b"},
        ],
        registry=ToggleOp,
    )
    assert len(patch) == 2
    assert patch[0].op == "toggle"
    assert len(patch[:1]) == 1
    assert [op.op for op in patch] == ["toggle", "toggle"]

    payload = json.loads(patch.to_string())
    assert payload[0]["op"] == "toggle"


def test_jsonpatch_rejects_invalid_registry_typeform() -> None:
    with pytest.raises(
        InvalidOperationRegistry,
        match="registry must be a union of concrete OperationSchemas",
    ):
        JsonPatch([], registry=cast(Any, int))


def test_parse_python_op_accepts_models_and_dicts() -> None:
    registry = _RegistrySpec.from_typeform(ToggleOp)
    op_from_dict = registry.parse_python_op({"op": "toggle", "path": "/a"})
    assert isinstance(op_from_dict, ToggleOp)

    op_instance = ToggleOp(path="/b")
    op_from_model = registry.parse_python_op(op_instance)
    assert op_from_model is op_instance


def test_parse_python_op_rejects_other_registry_models() -> None:
    standard = _RegistrySpec.from_typeform(StandardRegistry)
    op_instance = standard.parse_python_op({"op": "add", "path": "/a", "value": 1})

    registry = _RegistrySpec.from_typeform(ToggleOp)
    with pytest.raises(OperationNotRecognized):
        registry.parse_python_op(op_instance)


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

    slash = cast(Any, registry.parse_python_op({"op": "slash-op", "path": "/a/b"}))
    dot = cast(Any, registry.parse_python_op({"op": "dot-op", "path": "a.b"}))

    assert type(slash) is SlashOp
    assert type(dot) is DotOp


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
