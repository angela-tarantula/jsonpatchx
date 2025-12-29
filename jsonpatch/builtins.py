import copy
from collections.abc import Set
from typing import Final, Literal, Self, override

from pydantic import Field, model_validator

from jsonpatch.exceptions import InvalidOperationSchema, TestOpFailed
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONArray, JSONBoolean, JSONNumber, JSONPointer, JSONValue


class AddOp(OperationSchema):
    op: Literal["add"] = "add"
    path: JSONPointer[JSONValue]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.add(doc, self.value)


class RemoveOp(OperationSchema):
    op: Literal["remove"] = "remove"
    path: JSONPointer[JSONValue] = Field(min_length=1)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.remove(doc)


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

    @model_validator(mode="after")
    def _regect_proper_prefixes(self) -> Self:
        if self.from_.is_parent_of(self.path):
            raise InvalidOperationSchema(
                "pointer 'path' cannot be a child of pointer 'from'"
            )
        elif self.path.is_parent_of(self.from_):
            raise InvalidOperationSchema(
                "pointer 'from' cannot be a child of pointer 'path'"
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
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
        duplicate = copy.deepcopy(value)
        return AddOp(path=self.path, value=duplicate).apply(doc)


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


class _IncrementOp(OperationSchema):
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    value: JSONNumber = Field(gt=0, decimal_places=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        amount = self.path.get(doc)  # amount is a JSONNumber (inferred & enforced!)
        total = amount + self.value
        return AddOp(path=self.path, value=total).apply(doc)


class _AppendOp(OperationSchema):
    op: Literal["append"] = "append"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, self.value]).apply(doc)


class _ExtendOp(OperationSchema):
    op: Literal["extend"] = "extend"
    path: JSONPointer[JSONArray[JSONValue]]
    values: list[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, *self.values]).apply(doc)


class _ToggleBoolOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=not current).apply(doc)


class _SwapOp(OperationSchema):
    op: Literal["swap"] = "swap"
    a: JSONPointer[JSONValue]
    b: JSONPointer[JSONValue]

    @model_validator(mode="after")
    def _regect_proper_prefixes(self) -> Self:
        if self.a.is_parent_of(self.b):
            raise InvalidOperationSchema("pointer 'b' cannot be a child of pointer 'a'")
        elif self.b.is_parent_of(self.a):
            raise InvalidOperationSchema("pointer 'a' cannot be a child of pointer 'b'")
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        self.a.ptr
        value_a = self.a.get(doc)
        value_b = self.b.get(doc)
        doc = AddOp(path=self.a, value=value_b).apply(doc)
        return AddOp(path=self.b, value=value_a).apply(doc)
