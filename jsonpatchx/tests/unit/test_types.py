from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError
from pytest import Subtests

from jsonpatchx.exceptions import InvalidJSONPointer
from jsonpatchx.tests.unit.conftest import FullPointer, NotAFullPointer
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
    class BadPointer(FullPointer):
        def __init__(self, pointer: str) -> None:
            if not pointer:
                raise ValueError("BadPointer does not accept the empty string")

    with subtests.test("valid backend"):
        assert JSONPointer._implements_PointerBackend_protocol(FullPointer) is True

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
            JSONPointer._implements_PointerBackend_protocol(FullPointer("a/b"))


def test_resolve_strictest_backend(subtests: Subtests) -> None:
    class RegistryPointer(FullPointer):
        pass

    class BoundPointer(FullPointer):
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
