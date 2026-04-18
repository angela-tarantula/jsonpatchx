from __future__ import annotations

from typing import Generic, Literal, override

import pytest
from typing_extensions import TypeVar

from jsonpatchx.builtins import AddOp, RemoveOp, ReplaceOp
from jsonpatchx.exceptions import InvalidJSONPointer, PatchConflictError
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONBoolean, JSONBound, JSONValue
from tests.support.pointers import DotPointer


def test_jsonpointer_invalid_syntax() -> None:
    class ReadOp(OperationSchema):
        op: Literal["read"] = "read"
        path: JSONPointer[JSONValue]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc  # pragma: no cover

    with pytest.raises(InvalidJSONPointer):
        ReadOp.model_validate({"path": "/a~2"})


def test_jsonpointer_type_gating() -> None:
    class ToggleOp(OperationSchema):
        op: Literal["toggle"] = "toggle"
        path: JSONPointer[JSONBoolean]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc  # pragma: no cover

    op = ToggleOp.model_validate({"path": "/flag"})
    assert op.path.get({"flag": True}) is True

    with pytest.raises(PatchConflictError):
        op.path.get({"flag": 1})


def test_jsonpointer_backend_mismatch_parent_check() -> None:
    class DotOp(OperationSchema):
        op: Literal["dot"] = "dot"
        path: JSONPointer[JSONValue, DotPointer]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc  # pragma: no cover

    class SlashOp(OperationSchema):
        op: Literal["slash"] = "slash"
        path: JSONPointer[JSONValue]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc  # pragma: no cover

    dot = DotOp.model_validate({"path": "a.b"})
    slash = SlashOp.model_validate({"path": "/a/b"})

    with pytest.raises(InvalidJSONPointer):
        dot.path.is_parent_of(slash.path)


def test_composed_ops_preserve_custom_pointer_backend() -> None:
    class DotReplaceOp(OperationSchema):
        op: Literal["dot-replace"] = "dot-replace"
        path: JSONPointer[JSONValue, DotPointer]
        value: JSONValue

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return ReplaceOp(path=self.path, value=self.value).apply(doc)

    class DotMoveOp(OperationSchema):
        op: Literal["dot-move"] = "dot-move"
        from_: JSONPointer[JSONValue, DotPointer]
        path: JSONPointer[JSONValue, DotPointer]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            value = self.from_.get(doc)
            doc = RemoveOp(path=self.from_).apply(doc)
            return AddOp(path=self.path, value=value).apply(doc)

    replaced = DotReplaceOp.model_validate(
        {"path": "a.b", "value": 2},
    ).apply({"a": {"b": 1}})
    assert replaced == {"a": {"b": 2}}

    moved = DotMoveOp.model_validate(
        {"from_": "a.b", "path": "x.y"},
    ).apply({"a": {"b": 1}, "x": {}})
    assert moved == {"a": {}, "x": {"y": 1}}


def test_custom_generic_op_can_still_specialize_jsonpointer_type() -> None:

    T = TypeVar("T", default=JSONValue, bound=JSONBound)

    class TypedReplaceOp(OperationSchema, Generic[T]):
        op: Literal["typed-replace"] = "typed-replace"
        path: JSONPointer[T]
        value: T

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            doc = self.path.remove(doc)
            return self.path.add(doc, self.value)

    op = TypedReplaceOp[JSONBoolean].model_validate({"path": "/flag", "value": False})
    assert op.apply({"flag": True}) == {"flag": False}

    with pytest.raises(PatchConflictError):
        op.apply({"flag": 1})
