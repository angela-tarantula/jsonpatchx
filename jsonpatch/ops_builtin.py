from typing import Literal, override

from pydantic import Field

from jsonpatch.schema import OperationSchema, PatchSchema
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


BuiltinPatchSchema: PatchSchema = PatchSchema(
    AddOp, RemoveOp, ReplaceOp, MoveOp, CopyOp, TestOp
)

if __name__ == "__main__":
    raw = {"op": "add", "path": "/4", "value": "bar"}
    op = BuiltinPatchSchema.parse_op(raw)
    raw_patch = [
        {"op": "add", "path": "/foo", "value": "bar"},
        {"op": "remove", "path": "/foo"},
    ]
    ops = BuiltinPatchSchema.parse_patch(raw_patch)
