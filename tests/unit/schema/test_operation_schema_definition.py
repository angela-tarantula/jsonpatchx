from __future__ import annotations

from typing import Any, Literal, Self, cast, override

import pytest
from pydantic import ConfigDict, Field, TypeAdapter, ValidationError, model_validator
from pydantic.experimental.missing_sentinel import MISSING
from pytest import Subtests

from jsonpatchx import ReplaceOp
from jsonpatchx.exceptions import InvalidOperationDefinition
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import (
    JSONArray,
    JSONBoolean,
    JSONBound,
    JSONNull,
    JSONNumber,
    JSONObject,
    JSONString,
    JSONValue,
)


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
                op: Literal[1] = 1
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


def test_runtime_json_types_accept_missing() -> None:
    # MISSING is considered compatible with any type narrowing JSONValue.
    for json_type in (
        JSONBoolean,
        JSONNumber,
        JSONString,
        JSONNull,
        JSONArray[Any],
        JSONObject[Any],
        JSONValue,
        JSONBound,
    ):
        adapter = TypeAdapter(json_type)
        assert adapter.validate_python(MISSING) is MISSING


class TestAdvancedOperationSchema:
    @staticmethod
    def clamp_op() -> type[OperationSchema]:
        """
        Factory for a clamp operation schema with complex validation and OpenAPI schema.

        The model is built lazily so that any regression that breaks this model's construction
        does not prevent all other tests from running for clearer diagnosis.
        """

        class ClampOp(OperationSchema):
            model_config = ConfigDict(
                title="Clamp operation",
                validate_default=False,
                json_schema_extra={
                    "description": "Clamp a numeric value at path to the inclusive range [min, max].",
                    "anyOf": [{"required": ["min"]}, {"required": ["max"]}],
                },
            )

            op: Literal["clamp"] = "clamp"
            path: JSONPointer[JSONNumber] = Field(
                description="Pointer to the numeric value to clamp."
            )
            min: JSONNumber = Field(
                default=cast(JSONNumber, MISSING),
                description="Inclusive lower bound.",
            )
            max: JSONNumber = Field(
                default=cast(JSONNumber, MISSING),
                description="Inclusive upper bound.",
            )

            @model_validator(mode="after")
            def _validate_bounds(self) -> Self:
                has_min = "min" in self.model_fields_set
                has_max = "max" in self.model_fields_set

                if not has_min and not has_max:
                    raise ValueError("clamp requires at least one of min or max")
                if has_min and has_max and self.min > self.max:
                    raise ValueError("clamp requires min <= max")
                return self

            @override
            def apply(self, doc: JSONValue) -> JSONValue:
                current = self.path.get(doc)
                if "min" in self.model_fields_set:
                    current = max(self.min, current)
                if "max" in self.model_fields_set:
                    current = min(self.max, current)
                return ReplaceOp(path=self.path, value=current).apply(doc)

        return ClampOp

    def test_advanced_operation_schema_openapi(self) -> None:
        ClampOp = self.clamp_op()

        assert ClampOp.model_json_schema() == {
            "additionalProperties": True,
            "anyOf": [{"required": ["min"]}, {"required": ["max"]}],
            "description": "Clamp a numeric value at path to the inclusive range [min, max].",
            "properties": {
                "op": {
                    "const": "clamp",
                    "description": "The operation to perform.",
                    "title": "Op",
                    "type": "string",
                },
                "path": {
                    "description": "Pointer to the numeric value to clamp.",
                    "format": "json-pointer",
                    "title": "Path",
                    "type": "string",
                    "x-pointer-type-schema": {"type": "number"},
                },
                "min": {
                    "description": "Inclusive lower bound.",
                    "title": "Min",
                    "type": "number",
                },
                "max": {
                    "description": "Inclusive upper bound.",
                    "title": "Max",
                    "type": "number",
                },
            },
            "required": ["op", "path"],
            "title": "Clamp operation",
            "type": "object",
        }

    def test_advanced_operation_schema_runtime(self) -> None:
        ClampOp = self.clamp_op()

        ClampOp.model_validate({"path": "/count", "min": 3})
        ClampOp.model_validate({"path": "/count", "max": 9})
        ClampOp.model_validate({"path": "/count", "min": 3, "max": 9})

        with pytest.raises(ValidationError, match="at least one of min or max"):
            ClampOp.model_validate({"path": "/count"})

        with pytest.raises(ValidationError, match="min <= max"):
            ClampOp.model_validate({"path": "/count", "min": 10, "max": 1})

        assert JsonPatch(
            [{"op": "clamp", "path": "/count", "min": 3}], registry=ClampOp
        ).apply({"count": 1}) == {"count": 3}
        assert JsonPatch(
            [{"op": "clamp", "path": "/count", "max": 9}], registry=ClampOp
        ).apply({"count": 12}) == {"count": 9}
        assert JsonPatch(
            [{"op": "clamp", "path": "/count", "min": 3, "max": 9}],
            registry=ClampOp,
        ).apply({"count": 5}) == {"count": 5}
