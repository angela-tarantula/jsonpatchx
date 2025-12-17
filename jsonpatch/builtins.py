from collections.abc import Set
from typing import Final, Literal, override

from pydantic import Field

from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONNumber, JSONPointer, JSONValue


class AddOp(OperationSchema):
    op: Literal["add"] = "add"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class RemoveOp(OperationSchema):
    op: Literal["remove"] = "remove"
    path: JSONPointer[JSONValue] = Field(min_length=1)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class MoveOp(OperationSchema):
    op: Literal["move"] = "move"
    from_: JSONPointer[JSONValue] = Field(alias="from")
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class CopyOp(OperationSchema):
    op: Literal["copy"] = "copy"
    from_: JSONPointer[JSONValue] = Field(alias="from")
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class TestOp(OperationSchema):
    op: Literal["test"] = "test"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


STANDARD_OPS: Final[Set[type[OperationSchema]]] = frozenset(
    [
        AddOp,
        RemoveOp,
        ReplaceOp,
        MoveOp,
        CopyOp,
        TestOp,
    ]
)


# Example domain-specific ops:


class IncrementOp(OperationSchema):
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    value: JSONNumber = Field(gt=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class DecrementOp(OperationSchema):
    op: Literal["decrement"] = "decrement"
    path: JSONPointer[JSONNumber]
    value: JSONNumber = Field(lt=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError
