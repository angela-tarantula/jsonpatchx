from collections.abc import Iterable
from typing import Any, Literal, override

import pytest
from pydantic import TypeAdapter, ValidationError
from pytest import Subtests

from jsonpatchx.exceptions import InvalidJSONPointer, PatchConflictError
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import (
    JSONArray,
    JSONBoolean,
    JSONContainer,
    JSONNull,
    JSONNumber,
    JSONObject,
    JSONPointer,
    JSONString,
    JSONValue,
    PointerBackend,
)


def test_json_primitive_strict_types(subtests: Subtests) -> None:
    bool_adapter = TypeAdapter(JSONBoolean)
    number_adapter = TypeAdapter(JSONNumber)
    string_adapter = TypeAdapter(JSONString)
    null_adapter = TypeAdapter(JSONNull)

    with subtests.test("JSONBoolean"):
        bool_adapter.validate_python(True)
        bool_adapter.validate_python(False)
        for invalid in (1, "true", "False", 0):
            with pytest.raises(ValidationError):
                bool_adapter.validate_python(invalid)

    with subtests.test("JSONNumber"):
        number_adapter.validate_python(1)
        number_adapter.validate_python(1.5)
        for invalid in ("2", True, None):
            with pytest.raises(ValidationError):
                number_adapter.validate_python(invalid)

    with subtests.test("JSONString"):
        string_adapter.validate_python("ok")
        for invalid in (b"nope", 1, False):
            with pytest.raises(ValidationError):
                string_adapter.validate_python(invalid)

    with subtests.test("JSONNull"):
        null_adapter.validate_python(None)
        for invalid in ("null", 0, False):
            with pytest.raises(ValidationError):
                null_adapter.validate_python(invalid)


def test_json_container_strict_types(subtests: Subtests) -> None:
    array_adapter = TypeAdapter(JSONArray[Any])
    object_adapter = TypeAdapter(JSONObject[Any])
    container_adapter = TypeAdapter(JSONContainer[Any])

    with subtests.test("JSONArray"):
        array_adapter.validate_python([1, {"a": 2}, "ok"])
        array_adapter.validate_python([object()])
        for invalid in ({"a": 1}, "nope", (1, 2)):
            with pytest.raises(ValidationError):
                array_adapter.validate_python(invalid)

    with subtests.test("JSONObject"):
        object_adapter.validate_python({"a": 1, "b": object()})
        for invalid in (["nope"], "nope", {("k",): "nope"}):
            with pytest.raises(ValidationError):
                object_adapter.validate_python(invalid)

    with subtests.test("JSONContainer"):
        container_adapter.validate_python([object()])
        container_adapter.validate_python({"a": object()})
        for invalid in ("nope", (1, 2), {"a", "b"}):
            with pytest.raises(ValidationError):
                container_adapter.validate_python(invalid)


def test_jsonvalue_strict_types(subtests: Subtests) -> None:
    value_adapter = TypeAdapter(JSONValue)

    with subtests.test("jsonvalue accepts primitives"):
        for value in (True, 1, 1.5, "ok", None):
            value_adapter.validate_python(value)
        for invalid in (object(), b"bytes"):
            with pytest.raises(ValidationError):
                value_adapter.validate_python(invalid)

    with subtests.test("jsonvalue accepts containers of primitives"):
        value_adapter.validate_python([1, "two", None, False])
        value_adapter.validate_python({"a": 1, "b": "two", "c": None, "d": False})

    with subtests.test("jsonvalue accepts containers of containers of primitives"):
        value_adapter.validate_python([[1, 2], ["a", {"b": True}], [None]])
        value_adapter.validate_python({"a": {"b": 1, "c": None}, "d": [True, False]})

    with subtests.test("jsonvalue rejects non-primitives and invalid containers"):
        for invalid in (
            object(),
            [object()],
            {"a": object()},
            {1: "value"},
            [[object()]],
            {"a": {"b": object()}},
            {"a": [object()]},
        ):
            with pytest.raises(ValidationError):
                value_adapter.validate_python(invalid)


def test_pointer_backend_protocol_check(subtests: Subtests) -> None:
    class NotAFullPointer:
        def __init__(self, pointer: str) -> None:
            self._parts = [] if pointer == "" else pointer.split(".")

        @property
        def parts(self) -> list[str]:
            return self._parts

        @classmethod
        def from_parts(cls, parts: Iterable[Any]) -> GoodPointer:
            return cls(".".join(str(p) for p in parts))

        def __str__(self) -> str:
            return ".".join(self._parts)

        def __hash__(self) -> int:
            return hash(tuple(self._parts))

    class GoodPointer(NotAFullPointer):
        def resolve(self, doc: JSONValue) -> Any:
            cur: Any = doc
            for token in self._parts:
                cur = cur[token]
            return cur

    class BadPointer(GoodPointer):
        def __init__(self, pointer: str) -> None:
            if not pointer:
                raise ValueError("BadPointer does not accept the empty string")

    with subtests.test("valid backend"):
        assert JSONPointer._implements_PointerBackend_protocol(GoodPointer) is True

    with subtests.test("must be a class"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer._implements_PointerBackend_protocol(object())

    with subtests.test("require empty string"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer._implements_PointerBackend_protocol(BadPointer)

    with subtests.test("must implement all methods"):
        assert JSONPointer._implements_PointerBackend_protocol(NotAFullPointer) is False

    with subtests.test("must not be an instance"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer._implements_PointerBackend_protocol(GoodPointer("a/b"))


def test_resolve_strictest_backend(subtests: Subtests) -> None:
    class BasePointer(PointerBackend):
        def __init__(self, pointer: str) -> None:
            self._parts = [] if pointer == "" else pointer.split(".")

        @property
        def parts(self) -> list[str]:
            return self._parts

        @classmethod
        def from_parts(cls, parts: Iterable[Any]) -> "BasePointer":
            return cls(".".join(str(p) for p in parts))

        def resolve(self, doc: JSONValue) -> Any:
            cur: Any = doc
            for token in self._parts:
                cur = cur[token]
            return cur

        def __str__(self) -> str:
            return ".".join(self._parts)

        def __hash__(self) -> int:
            return hash(tuple(self._parts))

    class RegistryPointer(BasePointer):
        pass

    class BoundPointer(BasePointer):
        pass

    class ChildPointer(BoundPointer):
        pass

    with subtests.test("no backends"):
        assert JSONPointer._resolve_strictest_backend(None, None) is PointerBackend

    with subtests.test("registry only"):
        assert (
            JSONPointer._resolve_strictest_backend(RegistryPointer, None)
            is RegistryPointer
        )

    with subtests.test("bound only"):
        assert (
            JSONPointer._resolve_strictest_backend(None, BoundPointer) is BoundPointer
        )

    with subtests.test("same backend"):
        assert (
            JSONPointer._resolve_strictest_backend(BoundPointer, BoundPointer)
            is BoundPointer
        )

    with subtests.test("registry is subclass of bound"):
        assert (
            JSONPointer._resolve_strictest_backend(ChildPointer, BoundPointer)
            is ChildPointer
        )

    with subtests.test("mismatched backends"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer._resolve_strictest_backend(RegistryPointer, BoundPointer)


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

        @override
        def __hash__(self) -> int:
            return hash(tuple([self.__class__, *self._parts]))

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
