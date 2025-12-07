from typing import Literal, override

from pydantic import Field

from jsonpatch.operation_schema import OperationSchema
from jsonpatch.types import JsonPointerType, JsonValueType


class AddOp(OperationSchema):
    op: Literal["add"] = "add"
    path: JsonPointerType
    value: JsonValueType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        return NotImplemented


class RemoveOp(OperationSchema):
    op: Literal["remove"] = "remove"
    path: JsonPointerType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        return NotImplemented


class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JsonPointerType
    value: JsonValueType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        return NotImplemented


class MoveOp(OperationSchema):
    op: Literal["move"] = "move"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        return NotImplemented


class CopyOp(OperationSchema):
    op: Literal["copy"] = "copy"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        return NotImplemented


class TestOp(OperationSchema):
    op: Literal["test"] = "test"
    path: JsonPointerType
    value: JsonValueType

    @override
    def apply(self, doc: JsonValueType) -> JsonValueType:
        return NotImplemented
