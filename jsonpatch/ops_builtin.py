from typing import Annotated, Literal, TypeAlias, Union

from pydantic import Field, TypeAdapter

from jsonpatch.schema import OperationSchema, PatchSchema
from jsonpatch.types import JsonPointerType, JsonValueType


class AddOp(OperationSchema):
    op: Literal["add"] = "add"
    path: JsonPointerType
    value: JsonValueType


class RemoveOp(OperationSchema):
    op: Literal["remove"] = "remove"
    path: JsonPointerType


class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JsonPointerType
    value: JsonValueType


class MoveOp(OperationSchema):
    op: Literal["move"] = "move"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType


class CopyOp(OperationSchema):
    op: Literal["copy"] = "copy"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType


class TestOp(OperationSchema):
    op: Literal["test"] = "test"
    path: JsonPointerType
    value: JsonValueType


BuiltinOpUnion: TypeAlias = Annotated[
    Union[AddOp, RemoveOp, ReplaceOp, MoveOp, CopyOp, TestOp],
    Field(discriminator="op"),
]

BuiltinOpAdapter: TypeAdapter[BuiltinOpUnion] = TypeAdapter(BuiltinOpUnion)
BuiltinPatchAdapter: TypeAdapter[list[BuiltinOpUnion]] = TypeAdapter(
    list[BuiltinOpUnion]
)


BuiltinPatchSchema: PatchSchema = PatchSchema(
    AddOp, RemoveOp, ReplaceOp, MoveOp, CopyOp, TestOp
)

if __name__ == "__main__":
    raw = {"op": "add", "path": "/4", "value": "bar"}
    op = BuiltinOpAdapter.validate_python(raw)
    raw_patch = [
        {"op": "add", "path": "/foo", "value": "bar"},
        {"op": "remove", "path": "/foo"},
    ]

    ops = BuiltinPatchAdapter.validate_python(raw_patch)
    # -> list[AddOp | RemoveOp | ...]

    c = AddOp(path="/", value=3)
