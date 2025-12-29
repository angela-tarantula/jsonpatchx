import copy
from collections.abc import Set
from typing import Final, Literal, override

from pydantic import Field

from jsonpatch.exceptions import PatchApplicationError, TestOpFailed
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONNumber, JSONPointer, JSONValue


class AddOp(OperationSchema):
    op: Literal["add"] = "add"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.set(doc, self.value)


class RemoveOp(OperationSchema):
    op: Literal["remove"] = "remove"
    path: JSONPointer[JSONValue] = Field(min_length=1)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.delete(doc)


class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        doc = RemoveOp(path=self.path).apply(doc)
        return AddOp(path=self.path, value=self.value).apply(doc)


class MoveOp(OperationSchema):
    op: Literal["move"] = "move"
    from_: JSONPointer[JSONValue] = Field(alias="from")
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        if self.from_ == self.path:
            return doc
        if self.from_.is_parent_of(self.path):
            raise PatchApplicationError(
                f"path {self.from_!r} cannot be moved into its child path {self.path!r}"
            )
        value = self.from_.get(doc)
        doc = RemoveOp(path=self.from_).apply(doc)
        return AddOp(path=self.path, value=value).apply(doc)


class CopyOp(OperationSchema):
    op: Literal["copy"] = "copy"
    from_: JSONPointer[JSONValue] = Field(alias="from")
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value = self.from_.get(doc)
        return AddOp(path=self.path, value=copy.deepcopy(value)).apply(doc)


class TestOp(OperationSchema):
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
    value: JSONNumber = Field(gt=0, decimal_places=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        amount = self.path.get(doc)  # amount is a JSONNumber (inferred & enforced!)
        total = amount + self.value
        return AddOp(path=self.path, value=total).apply(doc)
