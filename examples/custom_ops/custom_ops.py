from __future__ import annotations

import os
from typing import Literal, Self, override

from pydantic import Field, model_validator

from jsonpatch import (
    AddOp,
    InvalidOperationSchema,
    OperationSchema,
    PatchApplicationError,
    ReplaceOp,
)
from jsonpatch.types import (
    JSONArray,
    JSONBoolean,
    JSONNumber,
    JSONObject,
    JSONPointer,
    JSONValue,
)

_DEMO_UNEXPECTED_ERRORS = os.getenv("JSONPATCH_DEMO_UNEXPECTED_ERRORS", "1") != "0"


class IncrementOp(OperationSchema):
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    value: JSONNumber = Field(gt=0, multiple_of=1.5)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        total = current + self.value
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
        return ReplaceOp(path=self.path, value=not current).apply(doc)


class EnsureObjectOp(OperationSchema):
    op: Literal["ensure_object"] = "ensure_object"
    path: JSONPointer[JSONObject[JSONValue]]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        try:
            current = self.path.ptr.resolve(doc)
        except Exception:
            return AddOp(path=self.path, value={}).apply(doc)
        if not isinstance(current, dict):
            raise PatchApplicationError(
                f"expected object at {str(self.path)!r}, got {type(current).__name__}"
            )
        return doc


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
        if _DEMO_UNEXPECTED_ERRORS and value_a == value_b:
            raise RuntimeError("boom")
        doc = AddOp(path=self.a, value=value_b).apply(doc)
        return AddOp(path=self.b, value=value_a).apply(doc)
