from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError
from pytest import Subtests

from jsonpatchx.exceptions import InvalidJSONPointer, PatchConflictError
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
    (
        "pointer_cls",
        "path",
        "parent_path",
        "child_path",
        "missing_path",
        "add_path",
        "parts",
    ),
    [
        (None, "/a/b", "/a", "/a/b/c", "/a/b/missing", "/a/new", ["a", "b"]),
        (DotPointer, "a.b", "a", "a.b.c", "a.b.missing", "a.new", ["a", "b"]),
    ],
)
def test_jsonpointer_public_methods_are_backend_agnostic(
    subtests: Subtests,
    pointer_cls: type[PointerBackend] | None,
    path: str,
    parent_path: str,
    child_path: str,
    missing_path: str,
    add_path: str,
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
        missing = adapter.validate_python(missing_path)
        assert missing.is_gettable(doc) is False

    with subtests.test("add"):
        add_ptr = adapter.validate_python(add_path)
        updated = add_ptr.add({"a": {"b": 1}}, "ok")
        assert updated["a"]["new"] == "ok"

    with subtests.test("is_addable"):
        add_ptr = adapter.validate_python(add_path)
        assert add_ptr.is_addable({"a": {"b": 1}}, "ok") is True
        assert child.is_addable(doc, "ok") is False

    with subtests.test("remove"):
        remove_ptr = adapter.validate_python(path)
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
        assert (
            JSONPointer._implements_PointerBackend_protocol(IncompletePointerBackend)
            is False
        )

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


@pytest.mark.parametrize(
    ("type_param", "valid_path", "valid_value", "wrong_values"),
    [
        (
            JSONBoolean,
            "/bool",
            True,
            [1, "ok", None, [1, 2], {"a": "b"}, [{"a": 1}, {"b": 2}]],
        ),
        (
            JSONNumber,
            "/num",
            1,
            [True, "ok", None, [1, 2], {"a": "b"}, [{"a": 1}, {"b": 2}]],
        ),
        (
            JSONString,
            "/str",
            "ok",
            [True, 1, None, [1, 2], {"a": "b"}, [{"a": 1}, {"b": 2}]],
        ),
        (
            JSONNull,
            "/null",
            None,
            [True, 1, "ok", [1, 2], {"a": "b"}, [{"a": 1}, {"b": 2}]],
        ),
        (
            JSONArray[JSONNumber],
            "/arr",
            [1, 2],
            [True, 1, "ok", None, {"a": "b"}, [{"a": 1}, {"b": 2}]],
        ),
        (
            JSONObject[JSONString],
            "/obj",
            {"a": "b"},
            [True, 1, "ok", None, [1, 2], [{"a": 1}, {"b": 2}]],
        ),
        (
            JSONArray[JSONObject[JSONNumber]],
            "/nested",
            [{"a": 1}, {"b": 2}],
            [True, 1, "ok", None, [1, 2], {"a": "b"}],
        ),
    ],
)
def test_jsonpointer_type_gating_methods(
    subtests: Subtests,
    type_param: Any,
    valid_path: str,
    valid_value: Any,
    wrong_values: list[Any],
) -> None:
    # Shared document with mixed types; each case targets a specific path.
    doc: JSONValue = {
        "bool": True,
        "num": 1,
        "str": "ok",
        "null": None,
        "arr": [1, 2],
        "obj": {"a": "b"},
        "nested": [{"a": 1}, {"b": 2}],
    }
    adapter = TypeAdapter(JSONPointer[type_param])
    ptr = adapter.validate_python(valid_path)

    with subtests.test("get / is_gettable"):
        assert ptr.get(doc) == valid_value
        assert ptr.is_gettable(doc) is True

    with subtests.test("get / is_gettable rejects wrong-type targets"):
        for key in doc.keys():
            if f"/{key}" == valid_path:
                continue
            # Typed pointer parsing doesn't validate against the document until get().
            other_ptr = adapter.validate_python(f"/{key}")
            with pytest.raises(PatchConflictError):
                other_ptr.get(doc)
            assert other_ptr.is_gettable(doc) is False

    with subtests.test("is_valid_target"):
        assert ptr.is_valid_target(valid_value) is True
        for v in wrong_values:
            assert ptr.is_valid_target(v) is False

    with subtests.test("add / is_addable"):
        assert ptr.is_addable(doc, valid_value) is True
        updated = ptr.add(doc.copy(), valid_value)
        assert updated[valid_path.lstrip("/")] == valid_value
        for v in wrong_values:
            assert ptr.is_addable(doc, v) is False
            with pytest.raises(PatchConflictError):
                ptr.add(doc.copy(), v)

    with subtests.test("remove"):
        removed = ptr.remove(doc.copy())
        assert valid_path.lstrip("/") not in removed


def test_jsonpointer_edge_cases(subtests: Subtests) -> None:
    adapter = TypeAdapter(JSONPointer[JSONValue])

    with subtests.test("root semantics"):
        root = adapter.validate_python("")
        assert root.get({"a": 1}) == {"a": 1}
        assert root.add({"a": 1}, {"b": 2}) == {"b": 2}
        assert root.remove({"a": 1}) is None

    with subtests.test("array index handling"):
        item = adapter.validate_python("/arr/0")
        assert item.get({"arr": [10, 20]}) == 10
        appended = adapter.validate_python("/arr/-").add({"arr": [10]}, 30)
        assert appended["arr"] == [10, 30]
        with pytest.raises(PatchConflictError):
            adapter.validate_python("/arr/-").remove({"arr": [10]})
        with pytest.raises(PatchConflictError):
            adapter.validate_python("/arr/2").remove({"arr": [10, 20]})

    with subtests.test("container type errors"):
        ptr = adapter.validate_python("/a/b")
        with pytest.raises(PatchConflictError):
            ptr.add({"a": 1}, "ok")
        with pytest.raises(PatchConflictError):
            ptr.remove({"a": 1})

    with subtests.test("parent/child edge cases"):
        parent = adapter.validate_python("/a")
        child = adapter.validate_python("/a/b")
        same = adapter.validate_python("/a")
        assert parent.is_parent_of(child) is True
        assert child.is_child_of(parent) is True
        assert parent.is_parent_of(same) is False


def test_jsonpointer_backend_reuse(subtests: Subtests) -> None:
    adapter = TypeAdapter(JSONPointer[JSONValue, DotPointer])
    ptr1 = adapter.validate_python("a.b")
    ptr2 = adapter.validate_python(ptr1)

    with subtests.test("reuses backend instance"):
        assert ptr2.ptr is ptr1.ptr
