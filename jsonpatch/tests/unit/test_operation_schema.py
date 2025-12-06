import pytest
from typing import Literal

from jsonpatch.exceptions import InvalidOperationSchema, InvalidPatchSchema
from jsonpatch.schema import OperationSchema, PatchSchema


def test_operation_schema_requires_op_field() -> None:
    with pytest.raises(InvalidOperationSchema):

        class NoOp(OperationSchema):
            path: str


def test_operation_schema_op_must_be_literal() -> None:
    with pytest.raises(InvalidOperationSchema):

        class NonLiteralOp(OperationSchema):
            op: str = "add"
            path: str


def test_operation_schema_op_literal_values_must_be_strings() -> None:
    with pytest.raises(InvalidOperationSchema):

        class NonStringLiteral(OperationSchema):
            op: Literal[1] = 1
            path: str


def test_patch_schema_requires_at_least_one_model() -> None:
    with pytest.raises(InvalidPatchSchema):
        PatchSchema()


def test_patch_schema_rejects_duplicate_op_identifiers() -> None:
    class FirstOp(OperationSchema):
        op: Literal["dup"] = "dup"
        path: str

    class SecondOp(OperationSchema):
        op: Literal["dup"] = "dup"
        path: str

    with pytest.raises(InvalidPatchSchema):
        PatchSchema(FirstOp, SecondOp)
