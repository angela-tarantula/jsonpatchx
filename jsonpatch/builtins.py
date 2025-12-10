from typing import Final, Literal, override

from pydantic import Field

from jsonpatch.schema import OperationSchema
from jsonpatch.types import JsonPointerType, JsonValueType


class AddOp(OperationSchema):
    op: Literal["add"] = "add"
    path: JsonPointerType
    value: JsonValueType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        raise NotImplementedError


class RemoveOp(OperationSchema):
    op: Literal["remove"] = "remove"
    path: JsonPointerType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        raise NotImplementedError


class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JsonPointerType
    value: JsonValueType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        raise NotImplementedError


class MoveOp(OperationSchema):
    op: Literal["move"] = "move"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        raise NotImplementedError


class CopyOp(OperationSchema):
    op: Literal["copy"] = "copy"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        raise NotImplementedError


class TestOp(OperationSchema):
    op: Literal["test"] = "test"
    path: JsonPointerType
    value: JsonValueType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        raise NotImplementedError


STANDARD_OPS: Final[frozenset[type[OperationSchema]]] = frozenset(
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
    path: JsonPointerType
    value: int = Field(gt=0)


class DecrementOp(OperationSchema):
    op: Literal["decrement"] = "decrement"
    path: JsonPointerType
    value: int = Field(lt=0)
