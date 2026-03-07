import json
from typing import Any, Generic, Literal, cast, override

import pytest
from pytest import Subtests
from typing_extensions import TypeVar

from jsonpatchx.exceptions import InvalidOperationRegistry, OperationNotRecognized
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.registry import OperationRegistry
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


def test_invalid_operation_registry(subtests: Subtests) -> None:
    class FirstOp(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return None  # pragma: no cover

    class SecondOp(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return None  # pragma: no cover

    class AbstractOp(OperationSchema):
        op: Literal["abstract"] = "abstract"

    with subtests.test("OperationRegistry requires at least one model"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry.__class_getitem__(())

    with subtests.test("OperationRegistry requires unique op identifiers"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry[FirstOp, SecondOp]

    with subtests.test("OperationRegistry rejects non-OperationSchema input"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry[str]

        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry[42]  # type: ignore[valid-type]

    with subtests.test("OperationRegistry rejects OperationSchema base class"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry[OperationSchema]

    with subtests.test("OperationRegistry rejects abstract OperationSchema subclasses"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry[AbstractOp]

    with subtests.test("OperationRegistry rejects OperationSchema instances"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry[FirstOp()]  # type: ignore[misc]

    with subtests.test("OperationRegistry rejects nested registries"):
        nested = OperationRegistry[FirstOp]
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry[nested, SecondOp]


def test_patch_schema_parse_happy_path(subtests: Subtests) -> None:
    class IncrementOp(OperationSchema):
        op: Literal["increment"] = "increment"
        path: str
        value: int = 1

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return None  # pragma: no cover

    class ToggleByPathOp(OperationSchema):
        op: Literal["toggle-by-path"] = "toggle-by-path"
        path: str

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return None  # pragma: no cover

    schema = OperationRegistry[IncrementOp, ToggleByPathOp]

    with subtests.test("parse_op succeeds"):
        op = schema.parse_python_op({"op": "increment", "path": "/foo", "value": 3})
        assert isinstance(op, IncrementOp)
        assert op.path == "/foo"
        assert op.value == 3

    with subtests.test("parse_patch succeeds"):
        patch = schema.parse_python_patch(
            [
                {"op": "increment", "path": "/foo", "value": 1},
                {"op": "toggle-by-path", "path": "/foo"},
            ]
        )
        op1, op2 = patch
        assert isinstance(op1, IncrementOp)
        assert isinstance(op2, ToggleByPathOp)
        assert op1.path == op2.path == "/foo"
        assert op1.value == 1


def test_operation_registry_preserves_explicit_pointer_backend(
    subtests: Subtests,
) -> None:
    class DotRemoveOp(OperationSchema):
        op: Literal["dot-remove"] = "dot-remove"
        path: JSONPointer[JSONValue, DotPointer]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc  # pragma: no cover

    with subtests.test("direct instantiation uses backend"):
        op = DotRemoveOp.model_validate({"path": "a.b"})
        assert isinstance(op.path.ptr, DotPointer)

    with subtests.test("operation registry preserves explicit pointer backend"):
        registry = OperationRegistry[DotRemoveOp]
        op = cast(
            DotRemoveOp, registry.parse_python_op({"op": "dot-remove", "path": "a.b"})
        )
        assert isinstance(op.path.ptr, DotPointer)


def test_registry_repr_and_hash() -> None:
    registry = OperationRegistry[ToggleOp]
    rep = repr(registry)
    assert "ToggleOp" in rep
    assert isinstance(hash(registry), int)


def test_registry_type_cache_reuses_registry_class() -> None:
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

    registry_a = OperationRegistry[FirstOp, SecondOp]
    registry_b = OperationRegistry[SecondOp, FirstOp]
    assert registry_a is registry_b


def test_registry_of_uses_same_cache_as_bracket_syntax() -> None:
    class FirstOp(OperationSchema):
        op: Literal["cache-of-first"] = "cache-of-first"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class SecondOp(OperationSchema):
        op: Literal["cache-of-second"] = "cache-of-second"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    from_brackets = OperationRegistry[FirstOp, SecondOp]
    from_of = OperationRegistry.of(SecondOp, FirstOp)

    assert from_of is from_brackets


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


def test_model_for_returns_registered_model_and_rejects_unknown() -> None:
    registry = OperationRegistry[ToggleOp]
    assert registry.model_for("toggle") is ToggleOp
    with pytest.raises(OperationNotRecognized):
        registry.model_for("not-allowed")


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

    registry_a = OperationRegistry[GenericOp[DotBackendA]]
    op_a = cast(Any, registry_a.parse_python_op({"op": "generic-op", "path": "a.b"}))
    assert isinstance(op_a.path.ptr, DotBackendA)

    registry_b = OperationRegistry[GenericOp[DotBackendB]]
    op_b = cast(Any, registry_b.parse_python_op({"op": "generic-op", "path": "a.b"}))
    assert isinstance(op_b.path.ptr, DotBackendB)


def test_registry_accepts_mixed_backends() -> None:
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

    registry = OperationRegistry[SlashOp, DotOp]

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

    registry = OperationRegistry[GenericOp[Backend1]]

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
