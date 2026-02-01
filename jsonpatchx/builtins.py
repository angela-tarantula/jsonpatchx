import copy
from typing import Final, Literal, Self, override

from pydantic import ConfigDict, Field, model_validator

from jsonpatchx.exceptions import OperationValidationError, TestOpFailed
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue


class AddOp(OperationSchema):
    """RFC 6902 add operation."""

    model_config = ConfigDict(
        title="Add operation",
        json_schema_extra={"description": "RFC 6902 add operation."},
    )

    op: Literal["add"] = "add"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.add(doc, self.value)


class RemoveOp(OperationSchema):
    """RFC 6902 remove operation. Removal of the root sets it to null."""

    model_config = ConfigDict(
        title="Remove operation",
        json_schema_extra={
            "description": "RFC 6902 remove operation. Removal of the root sets it to null."
        },
    )

    op: Literal["remove"] = "remove"
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.remove(doc)


class ReplaceOp(OperationSchema):
    """RFC 6902 replace operation."""

    model_config = ConfigDict(
        title="Replace operation",
        json_schema_extra={"description": "RFC 6902 replace operation."},
    )

    op: Literal["replace"] = "replace"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        doc = RemoveOp(path=self.path).apply(doc)
        return AddOp(path=self.path, value=self.value).apply(doc)


class MoveOp(OperationSchema):
    """RFC 6902 move operation."""

    model_config = ConfigDict(
        title="Move operation",
        json_schema_extra={"description": "RFC 6902 move operation."},
    )

    op: Literal["move"] = "move"
    from_: JSONPointer[JSONValue] = Field(alias="from")
    path: JSONPointer[JSONValue]

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.from_.is_parent_of(self.path):
            raise OperationValidationError(
                "pointer 'path' cannot be a child of pointer 'from'"
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value = self.from_.get(doc)
        doc = RemoveOp(path=self.from_).apply(doc)
        return AddOp(path=self.path, value=value).apply(doc)


class CopyOp(OperationSchema):
    """RFC 6902 copy operation."""

    model_config = ConfigDict(
        title="Copy operation",
        json_schema_extra={"description": "RFC 6902 copy operation."},
    )

    op: Literal["copy"] = "copy"
    from_: JSONPointer[JSONValue] = Field(alias="from")
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value = self.from_.get(doc)
        duplicate = copy.deepcopy(value)
        return AddOp(path=self.path, value=duplicate).apply(doc)


class TestOp(OperationSchema):
    """RFC 6902 test operation."""

    model_config = ConfigDict(
        title="Test operation",
        json_schema_extra={"description": "RFC 6902 test operation."},
    )

    op: Literal["test"] = "test"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        actual = self.path.get(doc)
        if actual != self.value:
            raise TestOpFailed(
                f"test at path {self.path!r} failed, got {actual!r} but expected {self.value!r}"
            )
        return doc


STANDARD_OPS: Final[tuple[type[OperationSchema], ...]] = (
    AddOp,
    CopyOp,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
