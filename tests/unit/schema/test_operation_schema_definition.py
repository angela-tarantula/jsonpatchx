from __future__ import annotations

from typing import Literal, override

import pytest
from pydantic import ValidationError
from pytest import Subtests

from jsonpatchx.exceptions import InvalidOperationDefinition
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue


def test_invalid_operation_schema_class(subtests: Subtests) -> None:
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
        with pytest.raises(
            (InvalidOperationDefinition, TypeError)
        ):  # TypeError for Py3.13- from get_type_hints

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
                return None  # pragma: no cover

        with pytest.raises(ValidationError):
            AppleOp(op="orange")  # type: ignore[arg-type]

    with subtests.test("pydantic enforces immutability of OperationSchemas"):

        class Orange(OperationSchema):
            op: Literal["orange"] = "orange"
            value: str

            @override
            def apply(self, doc: JSONValue) -> JSONValue:
                return None  # pragma: no cover

        orange = Orange(value="peel")

        with pytest.raises(ValidationError):
            orange.value = "ripe"  # type: ignore[misc]


def test_valid_operation_schema(subtests: Subtests) -> None:
    with subtests.test("valid op instantiation succeeds"):

        class IncrementOp(OperationSchema):
            op: Literal["increment"] = "increment"
            path: str
            value: int = 1

            @override
            def apply(self, doc: JSONValue) -> JSONValue:
                return None  # pragma: no cover

        op = IncrementOp(path="/", value=3)
        assert op.op == "increment"
        assert op.path == "/"
        assert op.value == 3

    with subtests.test("op can take multiple literals"):

        class OrganizeOp(OperationSchema):
            op: Literal["organize", "organise"]

            @override
            def apply(self, doc: JSONValue) -> JSONValue:
                return None  # pragma: no cover

        OrganizeOp(op="organize")
        OrganizeOp(op="organise")


def test_jsonvalue_accepts_json_types() -> None:
    class ValueOp(OperationSchema):
        op: Literal["value"] = "value"
        value: JSONValue

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc  # pragma: no cover

    valid_values: list[JSONValue] = [
        True,
        1,
        1.5,
        "ok",
        None,
        [1, "two"],
        {"a": 1, "b": False},
    ]
    for value in valid_values:
        op = ValueOp(value=value)
        assert op.value == value

    with pytest.raises(ValidationError):
        ValueOp(value=set([1, 2]))  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        ValueOp(value=object())  # type: ignore[arg-type]
