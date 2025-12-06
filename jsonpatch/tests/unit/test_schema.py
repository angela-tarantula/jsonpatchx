from typing import Literal

import pytest
from pydantic import ValidationError
from pytest import Subtests

from jsonpatch.exceptions import InvalidOperationSchema, InvalidPatchSchema
from jsonpatch.schema import OperationSchema, PatchSchema


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


def test_invalid_patch_schema(subtests: Subtests) -> None:
    with subtests.test("PatchSchema requires at least one model"):
        with pytest.raises(InvalidPatchSchema):
            PatchSchema()

    with subtests.test("PatchSchema rejects duplicate op identifiers"):

        class FirstOp(OperationSchema):
            op: Literal["dup"] = "dup"
            path: str

        class SecondOp(OperationSchema):
            op: Literal["dup"] = "dup"
            path: str

        with pytest.raises(InvalidPatchSchema):
            PatchSchema(FirstOp, SecondOp)


def test_valid_operation_schema(subtests: Subtests) -> None:
    class IncrementOp(OperationSchema):
        op: Literal["increment"] = "increment"
        path: str
        value: int = 1

    with subtests.test("pydantic enforces op literal"):
        with pytest.raises(ValidationError):
            IncrementOp(op="add", path="/", value=3)  # type: ignore[arg-type]

    with subtests.test("valid op instantiation succeeds"):
        op = IncrementOp(path="/", value=3)
        assert op.op == "increment"
        assert op.path == "/"
        assert op.value == 3


def test_patch_schema_parse_happy_path(subtests: Subtests) -> None:
    class IncrementOp(OperationSchema):
        op: Literal["increment"] = "increment"
        path: str
        value: int = 1

    class ToggleOp(OperationSchema):
        op: Literal["toggle"] = "toggle"
        path: str

    schema = PatchSchema(IncrementOp, ToggleOp)

    with subtests.test("parse_op succeeds"):
        op = schema.parse_op({"op": "increment", "path": "/foo", "value": 3})
        assert isinstance(op, IncrementOp)
        assert op.path == "/foo"
        assert op.value == 3

    with subtests.test("parse_patch succeeds"):
        patch = schema.parse_patch(
            [
                {"op": "increment", "path": "/foo", "value": 1},
                {"op": "toggle", "path": "/foo"},
            ]
        )
        assert [type(p) for p in patch] == [IncrementOp, ToggleOp]
