from typing import Literal, Self, override

from pydantic import Field, model_validator

from jsonpatch import AddOp
from jsonpatch.exceptions import InvalidOperationSchema
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONArray, JSONBoolean, JSONNumber, JSONPointer, JSONValue


class IncrementOp(OperationSchema):
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    value: JSONNumber = Field(gt=0, decimal_places=0)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        amount = self.path.get(doc)
        total = amount + self.value
        return AddOp(path=self.path, value=total).apply(doc)


class AppendOp(OperationSchema):
    op: Literal["append"] = "append"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, self.value]).apply(doc)


class ExtendOp(OperationSchema):
    op: Literal["extend"] = "extend"
    path: JSONPointer[JSONArray[JSONValue]]
    values: list[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, *self.values]).apply(doc)


class ToggleBoolOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=not current).apply(doc)


class SwapOp(OperationSchema):
    op: Literal["swap"] = "swap"
    a: JSONPointer[JSONValue]
    b: JSONPointer[JSONValue]

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.a.is_parent_of(self.b):
            raise InvalidOperationSchema("pointer 'b' cannot be a child of pointer 'a'")
        if self.b.is_parent_of(self.a):
            raise InvalidOperationSchema("pointer 'a' cannot be a child of pointer 'b'")
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value_a = self.a.get(doc)
        value_b = self.b.get(doc)
        doc = AddOp(path=self.a, value=value_b).apply(doc)
        return AddOp(path=self.b, value=value_a).apply(doc)
