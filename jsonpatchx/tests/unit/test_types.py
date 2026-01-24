from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError
from pytest import Subtests

from jsonpatchx.exceptions import InvalidJSONPointer
from jsonpatchx.tests.unit.conftest import DotPointer, IncompletePointerBackend
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


@pytest.mark.parametrize(
    ("pointer_cls", "path", "parent_path", "child_path", "parts"),
    [
        (None, "/a/b", "/a", "/a/b/c", ["a", "b"]),
        (DotPointer, "a.b", "a", "a.b.c", ["a", "b"]),
    ],
)
def test_jsonpointer_public_methods(
    subtests: Subtests,
    pointer_cls: type[PointerBackend] | None,
    path: str,
    parent_path: str,
    child_path: str,
    parts: list[str],
) -> None:
    doc = {"a": {"b": 1, "c": {"d": 2}}, "arr": [10, 20]}

    if pointer_cls is None:
        adapter = TypeAdapter(JSONPointer[JSONValue])
        bool_adapter = TypeAdapter(JSONPointer[JSONBoolean])
    else:
        adapter = TypeAdapter(JSONPointer[JSONValue, DotPointer])
        bool_adapter = TypeAdapter(JSONPointer[JSONBoolean, DotPointer])

    ptr = adapter.validate_python(path)
    parent = adapter.validate_python(parent_path)
    child = adapter.validate_python(child_path)

    with subtests.test("ptr"):
        assert ptr.ptr is not None

    with subtests.test("parts"):
        assert list(ptr.parts) == parts

    with subtests.test("type_param"):
        assert ptr.type_param is JSONValue

    with subtests.test("is_root"):
        assert ptr.is_root() is False
        root = adapter.validate_python("")
        assert root.is_root() is True

    with subtests.test("is_parent_of"):
        assert parent.is_parent_of(ptr) is True
        assert ptr.is_parent_of(parent) is False

    with subtests.test("is_child_of"):
        assert child.is_child_of(ptr) is True
        assert ptr.is_child_of(child) is False

    with subtests.test("is_valid_target"):
        bool_ptr = bool_adapter.validate_python(parent_path)
        assert bool_ptr.is_valid_target(True) is True
        assert bool_ptr.is_valid_target(1) is False

    with subtests.test("get"):
        assert ptr.get(doc) == 1

    with subtests.test("is_gettable"):
        assert ptr.is_gettable(doc) is True
        missing = adapter.validate_python(
            f"{path}.missing" if pointer_cls else f"{path}/missing"
        )
        assert missing.is_gettable(doc) is False

    with subtests.test("add"):
        add_path = f"{parent_path}.new" if pointer_cls else f"{parent_path}/new"
        add_ptr = adapter.validate_python(add_path)
        updated = add_ptr.add({"a": {"b": 1}}, "ok")
        assert updated["a"]["new"] == "ok"

    with subtests.test("is_addable"):
        add_path = f"{parent_path}.new" if pointer_cls else f"{parent_path}/new"
        add_ptr = adapter.validate_python(add_path)
        assert add_ptr.is_addable({"a": {"b": 1}}, "ok") is True
        assert child.is_addable(doc, "ok") is False

    with subtests.test("remove"):
        remove_path = f"{parent_path}.b" if pointer_cls else f"{parent_path}/b"
        remove_ptr = adapter.validate_python(remove_path)
        removed = remove_ptr.remove({"a": {"b": 1}})
        assert "b" not in removed["a"]

    with subtests.test("__str__"):
        assert str(ptr) == path


def test_pointer_backend_protocol_check(subtests: Subtests) -> None:
    class BadPointer(DotPointer):
        def __init__(self, pointer: str) -> None:
            if not pointer:
                raise ValueError("BadPointer does not accept the empty string")

    with subtests.test("valid backend"):
        assert JSONPointer._implements_PointerBackend_protocol(DotPointer) is True

    with subtests.test("must be a class"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer._implements_PointerBackend_protocol(object())

    with subtests.test("require empty string"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer._implements_PointerBackend_protocol(BadPointer)

    with subtests.test("must implement all methods"):
        assert JSONPointer._implements_PointerBackend_protocol(IncompletePointerBackend) is False

    with subtests.test("must not be an instance"):
        with pytest.raises(InvalidJSONPointer):
            JSONPointer._implements_PointerBackend_protocol(DotPointer("a/b"))


def test_resolve_strictest_backend(subtests: Subtests) -> None:
    class RegistryPointer(DotPointer):
        pass

    class BoundPointer(DotPointer):
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
