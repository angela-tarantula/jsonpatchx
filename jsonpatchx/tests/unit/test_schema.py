from collections.abc import Iterable
from typing import Any, Literal, cast, override

import pytest
from pydantic import ValidationError
from pytest import Subtests

from jsonpatchx.exceptions import (
    InvalidJSONPointer,
    InvalidOperationDefinition,
    InvalidOperationRegistry,
)
from jsonpatchx.registry import GenericOperationRegistry, OperationRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONPointer, JSONValue, PointerBackend


def test_invalid_operation_schema(subtests: Subtests) -> None:
    with subtests.test("OperationSchema requires op field"):
        with pytest.raises(InvalidOperationDefinition):

            class NoOp(OperationSchema):
                path: str

    with subtests.test("OperationSchema op must be Literal"):
        with pytest.raises(InvalidOperationDefinition):

            class NonLiteralOp(OperationSchema):
                op: str = "add"
                path: str

    with subtests.test("OperationSchema op literal must declare at least one value"):
        with pytest.raises(InvalidOperationDefinition):

            class EmptyLiteral(OperationSchema):
                op: Literal  # type: ignore[valid-type]
                path: str

    with subtests.test("OperationSchema op literal values must be strings"):
        with pytest.raises(InvalidOperationDefinition):

            class NonStringLiteral(OperationSchema):
                op: Literal[1] = 1  # type: ignore[assignment]
                path: str

    with subtests.test("pydantic enforces field type hints"):

        class AppleOp(OperationSchema):
            op: Literal["apple"]

            @override
            def apply(self, doc: JSONValue) -> JSONValue:
                return None

        with pytest.raises(ValidationError):
            AppleOp(op="orange")  # type: ignore[arg-type]

    with subtests.test("pydantic enforces immutability of OperationSchemas"):

        class Orange(OperationSchema):
            op: Literal["orange"] = "orange"
            value: str

            @override
            def apply(self, doc: JSONValue) -> JSONValue:
                return None

        orange = Orange(value="peel")

        with pytest.raises(ValidationError):
            orange.value = "ripe"  # type: ignore[misc]


def test_invalid_operation_registry(subtests: Subtests) -> None:
    class FirstOp(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return None

    class SecondOp(OperationSchema):
        op: Literal["dup"] = "dup"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return None

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


def test_valid_operation_schema(subtests: Subtests) -> None:
    with subtests.test("valid op instantiation succeeds"):

        class IncrementOp(OperationSchema):
            op: Literal["increment"] = "increment"
            path: str
            value: int = 1

            @override
            def apply(self, doc: JSONValue) -> JSONValue:
                return None

        op = IncrementOp(path="/", value=3)
        assert op.op == "increment"
        assert op.path == "/"
        assert op.value == 3

    with subtests.test("op can take multiple literals"):

        class OrganizeOp(OperationSchema):
            op: Literal["organize", "organise"]

            @override
            def apply(self, doc: JSONValue) -> JSONValue:
                return None

        OrganizeOp(op="organize")
        OrganizeOp(op="organise")


def test_patch_schema_parse_happy_path(subtests: Subtests) -> None:
    class IncrementOp(OperationSchema):
        op: Literal["increment"] = "increment"
        path: str
        value: int = 1

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return None

    class ToggleOp(OperationSchema):
        op: Literal["toggle"] = "toggle"
        path: str

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return None

    schema = OperationRegistry[IncrementOp, ToggleOp]

    with subtests.test("parse_op succeeds"):
        op = schema.parse_python_op({"op": "increment", "path": "/foo", "value": 3})
        assert isinstance(op, IncrementOp)
        assert op.path == "/foo"
        assert op.value == 3

    with subtests.test("parse_patch succeeds"):
        patch = schema.parse_python_patch(
            [
                {"op": "increment", "path": "/foo", "value": 1},
                {"op": "toggle", "path": "/foo"},
            ]
        )
        op1, op2 = patch
        assert isinstance(op1, IncrementOp)
        assert isinstance(op2, ToggleOp)
        assert op1.path == op2.path == "/foo"
        assert op1.value == 1


def test_pointer_backend_binding(subtests: Subtests) -> None:
    class DotPointer(PointerBackend):
        def __init__(self, pointer: str) -> None:
            self._parts = [] if pointer == "" else pointer.split(".")

        @property
        @override
        def parts(self) -> list[str]:
            return self._parts

        @classmethod
        @override
        def from_parts(cls, parts: Iterable[Any]) -> "DotPointer":
            return cls(".".join(parts))

        @override
        def resolve(self, doc: JSONValue) -> Any:
            cur: Any = doc
            for token in self._parts:
                cur = cur[token]
            return cur

        @override
        def __str__(self) -> str:
            return ".".join(self._parts)

    class DotRemoveOp(OperationSchema):
        op: Literal["dot-remove"] = "dot-remove"
        path: JSONPointer[JSONValue, DotPointer]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    with subtests.test("direct instantiation uses backend"):
        op = DotRemoveOp.model_validate({"path": "a.b"})
        assert isinstance(op.path.ptr, DotPointer)

    with subtests.test("registry backend mismatch fails"):
        registry_1 = OperationRegistry[DotRemoveOp]
        with pytest.raises(InvalidJSONPointer):
            registry_1.parse_python_op({"op": "dot-remove", "path": "a.b"})

    with subtests.test("registry backend match succeeds"):
        registry_2 = GenericOperationRegistry[DotRemoveOp, DotPointer]
        op = cast(
            DotRemoveOp, registry_2.parse_python_op({"op": "dot-remove", "path": "a.b"})
        )
        assert isinstance(op.path.ptr, DotPointer)
