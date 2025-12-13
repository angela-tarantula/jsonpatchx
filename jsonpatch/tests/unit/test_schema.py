from typing import Literal, override

import pytest
from pydantic import ValidationError
from pytest import Subtests

from jsonpatch.exceptions import InvalidOperationRegistry, InvalidOperationSchema
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONValue


def test_invalid_operation_schema(subtests: Subtests) -> None:
    with subtests.test("OperationSchema requires op field"):
        with pytest.raises(InvalidOperationSchema):

            class NoOp(OperationSchema):
                path: str

    with subtests.test("OperationSchema op must be Literal"):
        with pytest.raises(InvalidOperationSchema):

            class NonLiteralOp(OperationSchema):
                op: str = "add"
                path: str

    with subtests.test("OperationSchema op literal must declare at least one value"):
        with pytest.raises(InvalidOperationSchema):

            class EmptyLiteral(OperationSchema):
                op: Literal  # type: ignore[valid-type]
                path: str

    with subtests.test("OperationSchema op literal values must be strings"):
        with pytest.raises(InvalidOperationSchema):

            class NonStringLiteral(OperationSchema):
                op: Literal[1] = 1
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
            orange.value = "ripe"


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
            OperationRegistry()

    with subtests.test("OperationRegistry requires unique op identifiers"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry(FirstOp, SecondOp)

    with subtests.test("OperationRegistry rejects non-OperationSchema input"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry(str)  # type: ignore[arg-type]

        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry(42)  # type: ignore[arg-type]

    with subtests.test("OperationRegistry rejects OperationSchema base class"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry(OperationSchema)  # type: ignore[type-abstract]

    with subtests.test("OperationRegistry rejects abstract OperationSchema subclasses"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry(AbstractOp)  # type: ignore[type-abstract]

    with subtests.test("OperationRegistry rejects OperationSchema instances"):
        with pytest.raises(InvalidOperationRegistry):
            OperationRegistry(FirstOp())  # type: ignore[arg-type]


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

    schema = OperationRegistry(IncrementOp, ToggleOp)

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
