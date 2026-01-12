from collections.abc import Iterable
from typing import Any, Literal, override

import pytest
from pydantic import ValidationError

from jsonpatchx.exceptions import InvalidJSONPointer, PatchConflictError
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import (
    JSONBoolean,
    JSONPointer,
    JSONValue,
    PointerBackend,
)


def test_jsonvalue_accepts_json_types() -> None:
    class ValueOp(OperationSchema):
        op: Literal["value"] = "value"
        value: JSONValue

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    valid_values: list[JSONValue] = [
        True,
        1,
        1.5,
        "ok",
        None,
        [1, "two"],
        {"a": 1, "b": False},
    ]
    for value in valid_values:
        op = ValueOp(value=value)
        assert op.value == value

    with pytest.raises(ValidationError):
        ValueOp(value=set([1, 2]))  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        ValueOp(value=object())  # type: ignore[arg-type]


def test_jsonpointer_invalid_syntax() -> None:
    class ReadOp(OperationSchema):
        op: Literal["read"] = "read"
        path: JSONPointer[JSONValue]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    with pytest.raises(InvalidJSONPointer):
        ReadOp.model_validate({"path": "/a~2"})


def test_jsonpointer_type_gating() -> None:
    class ToggleOp(OperationSchema):
        op: Literal["toggle"] = "toggle"
        path: JSONPointer[JSONBoolean]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    op = ToggleOp.model_validate({"path": "/flag"})
    assert op.path.get({"flag": True}) is True

    with pytest.raises(PatchConflictError):
        op.path.get({"flag": 1})


def test_jsonpointer_backend_mismatch_parent_check() -> None:
    class DotPointer(PointerBackend):
        def __init__(self, pointer: str) -> None:
            self._parts = [] if pointer == "" else pointer.split(".")

        @property
        @override
        def parts(self) -> list[str]:
            return self._parts

        @classmethod
        @override
        def from_parts(cls, parts: Iterable[Any]) -> "DotPointer":
            return cls(".".join(parts))

        @override
        def resolve(self, doc: JSONValue) -> Any:
            cur: Any = doc
            for token in self._parts:
                cur = cur[token]
            return cur

        @override
        def __str__(self) -> str:
            return ".".join(self._parts)

    class DotOp(OperationSchema):
        op: Literal["dot"] = "dot"
        path: JSONPointer[JSONValue, DotPointer]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    class SlashOp(OperationSchema):
        op: Literal["slash"] = "slash"
        path: JSONPointer[JSONValue]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    dot = DotOp.model_validate({"path": "a.b"})
    slash = SlashOp.model_validate({"path": "/a/b"})

    with pytest.raises(InvalidJSONPointer):
        dot.path.is_parent_of(slash.path)
