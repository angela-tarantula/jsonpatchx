from collections.abc import Set
from typing import Final, Literal, override

from pydantic import Field

from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONPointer, JSONValue


class AddOp(OperationSchema):
    op: Literal["add"] = "add"
    path: JSONPointer
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class RemoveOp(OperationSchema):
    op: Literal["remove"] = "remove"
    path: JSONPointer

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JSONPointer
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class MoveOp(OperationSchema):
    op: Literal["move"] = "move"
    from_: JSONPointer = Field(alias="from")
    path: JSONPointer

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class CopyOp(OperationSchema):
    op: Literal["copy"] = "copy"
    from_: JSONPointer = Field(alias="from")
    path: JSONPointer

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise NotImplementedError


class TestOp(OperationSchema):
    op: Literal["test"] = "test"
    path: JSONPointer
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
    path: JSONPointer
    value: int = Field(gt=0)


class DecrementOp(OperationSchema):
    op: Literal["decrement"] = "decrement"
    path: JSONPointer
    value: int = Field(lt=0)
