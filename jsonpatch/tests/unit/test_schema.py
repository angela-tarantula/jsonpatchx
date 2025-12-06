from typing import Literal

import pytest
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
