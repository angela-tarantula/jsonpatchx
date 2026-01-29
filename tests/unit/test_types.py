from typing import Any, Final

import pytest
from jsonpointer import JsonPointer as RFC6901JsonPointer
from pydantic import TypeAdapter, ValidationError
from pytest import Subtests

from jsonpatchx.exceptions import InvalidJSONPointer, PatchConflictError
from jsonpatchx.types import (
    _POINTER_BACKEND_CTX_KEY,
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
from tests.unit.conftest import (
    AnotherIncompletePointerBackend,
    DotPointer,
    IncompletePointerBackend,
)

JSON_TYPE_VALIDATION_TEST_CASES: Final[list[tuple[str, object, set[str]]]] = [
    # (label, value, allowed adapter names)
    ("bool-true", True, {"JSONBoolean", "JSONValue"}),
    ("bool-false", False, {"JSONBoolean", "JSONValue"}),
    ("int", 1, {"JSONNumber", "JSONValue"}),
    ("float", 1.5, {"JSONNumber", "JSONValue"}),
    ("string", "ok", {"JSONString", "JSONValue"}),
    ("null", None, {"JSONNull", "JSONValue"}),
    (
        "array-simple",
        [1, {"a": 2}, "ok"],
        {"JSONArray", "JSONContainer", "JSONValue"},
    ),
    ("array-object-item", [object()], {"JSONArray", "JSONContainer"}),
    ("array-bytes-item", [b"bytes"], {"JSONArray", "JSONContainer"}),
    (
        "object-simple",
        {"a": 1, "b": "ok", "c": None, "d": True},
        {"JSONObject", "JSONContainer", "JSONValue"},
    ),
    ("object-any", {"a": 1, "b": object()}, {"JSONObject", "JSONContainer"}),
    (
        "nested",
        {"a": [1, {"b": [True, None, 3.5]}], "c": {"d": "ok"}},
        {"JSONObject", "JSONContainer", "JSONValue"},
    ),
    ("bytes", b"bytes", set()),
    ("object", object(), set()),
    ("tuple", (1, 2), set()),
    ("set", {"a", "b"}, set()),
    ("dict-non-str-key", {1: "nope"}, set()),
]


@pytest.mark.parametrize(
    "json_type",
    [
        JSONBoolean,
        JSONNumber,
        JSONString,
        JSONNull,
        JSONArray[Any],
        JSONObject[Any],
        JSONContainer[Any],
        JSONValue,
    ],
)
def test_json_type_validations(subtests: Subtests, json_type: Any) -> None:
    name = json_type.__name__
    adapter = TypeAdapter(json_type)
    for label, value, allowed in JSON_TYPE_VALIDATION_TEST_CASES:
        if name in allowed:
            with subtests.test(f"{name} accepts {label}"):
                adapter.validate_python(value)
        else:
            with subtests.test(f"{name} rejects {label}"):
                with pytest.raises(ValidationError):
                    adapter.validate_python(value)


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


def test_pointer_backend_binding_with_context(subtests: Subtests) -> None:
    class RegistryPointer(DotPointer):
        pass

    class BoundPointer(DotPointer):
        pass

    class ChildPointer(BoundPointer):
        pass

    def _validate(
        pointer_type: type[JSONPointer],
        path: str,
        registry_backend: type[PointerBackend] | None,
    ) -> JSONPointer:
        adapter = TypeAdapter(pointer_type)
        context = (
            None
            if registry_backend is None
            else {_POINTER_BACKEND_CTX_KEY: registry_backend}
        )
        return adapter.validate_python(path, context=context)

    with subtests.test("no backends"):
        ptr = _validate(JSONPointer[JSONValue], "/a", None)
        assert isinstance(ptr.ptr, RFC6901JsonPointer)

    with subtests.test("context PointerBackend treated as default"):
        ptr = _validate(JSONPointer[JSONValue], "/a", PointerBackend)
        assert isinstance(ptr.ptr, RFC6901JsonPointer)

    with subtests.test("registry only"):
        ptr = _validate(JSONPointer[JSONValue], "a.b", RegistryPointer)
        assert isinstance(ptr.ptr, RegistryPointer)

    with subtests.test("bound only"):
        ptr = _validate(JSONPointer[JSONValue, BoundPointer], "a.b", None)
        assert isinstance(ptr.ptr, BoundPointer)

    with subtests.test("bound PointerBackend treated as default"):
        ptr = _validate(JSONPointer[JSONValue, PointerBackend], "/a", None)
        assert isinstance(ptr.ptr, RFC6901JsonPointer)

    with subtests.test("both PointerBackend treated as default"):
        ptr = _validate(JSONPointer[JSONValue, PointerBackend], "/a", PointerBackend)
        assert isinstance(ptr.ptr, RFC6901JsonPointer)

    with subtests.test("same backend"):
        ptr = _validate(JSONPointer[JSONValue, BoundPointer], "a.b", BoundPointer)
        assert isinstance(ptr.ptr, BoundPointer)

    with subtests.test("registry is subclass of bound"):
        ptr = _validate(JSONPointer[JSONValue, BoundPointer], "a.b", ChildPointer)
        assert isinstance(ptr.ptr, ChildPointer)

    with subtests.test("mismatched backends"):
        with pytest.raises(InvalidJSONPointer):
            _validate(JSONPointer[JSONValue, BoundPointer], "a.b", RegistryPointer)


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
        with pytest.raises(PatchConflictError):
            adapter.validate_python("/arr/-1").remove({"arr": [10, 20]})
        with pytest.raises(PatchConflictError):
            adapter.validate_python("/arr/nope").remove({"arr": [10, 20]})

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


def test_jsonpointer_type_args_validation(subtests: Subtests) -> None:
    with subtests.test("invalid type param"):
        with pytest.raises(InvalidJSONPointer):
            TypeAdapter(JSONPointer[int()])

    with subtests.test("not enough args"):
        with pytest.raises(TypeError):
            TypeAdapter(JSONPointer)

    with subtests.test("too many args"):
        with pytest.raises(TypeError):
            TypeAdapter(JSONPointer[JSONValue, DotPointer, int])

    with subtests.test("invalid backend"):
        for invalid_backend in [
            object,
            object(),
            JSONValue,
            str,
            IncompletePointerBackend,
            AnotherIncompletePointerBackend,
            DotPointer(""),
            "DotPointer",  # forward references disallowed for predictability
        ]:
            with pytest.raises(InvalidJSONPointer):
                adapter = TypeAdapter(JSONPointer[JSONValue, invalid_backend])
                adapter.validate_python("")

    with subtests.test("valid backend"):
        for valid_backend in [
            PointerBackend,  # default backend
            DotPointer,
            RFC6901JsonPointer,
        ]:
            adapter = TypeAdapter(JSONPointer[JSONValue, valid_backend])
            adapter.validate_python("")


def test_jsonpointer_backend_cache_identity(subtests: Subtests) -> None:
    with subtests.test("default backend cache"):
        adapter = TypeAdapter(JSONPointer[JSONValue])
        p1 = adapter.validate_python("/a")
        p2 = adapter.validate_python("/a")
        assert p1.ptr is p2.ptr

    with subtests.test("custom backend cache"):
        adapter = TypeAdapter(JSONPointer[JSONValue, DotPointer])
        p1 = adapter.validate_python("a.b")
        p2 = adapter.validate_python("a.b")
        assert p1.ptr is p2.ptr


def test_jsonpointer_covariance_narrow_to_wide(subtests: Subtests) -> None:
    adapter_bool = TypeAdapter(JSONPointer[bool])
    adapter_int = TypeAdapter(JSONPointer[int])
    adapter_number = TypeAdapter(JSONPointer[JSONNumber])
    adapter_value = TypeAdapter(JSONPointer[JSONValue])

    with subtests.test("narrow to wide passes"):
        p_bool = adapter_bool.validate_python("/x")
        assert adapter_int.validate_python(p_bool) == p_bool
        assert adapter_number.validate_python(p_bool) == p_bool
        assert adapter_value.validate_python(p_bool) == p_bool


def test_jsonpointer_covariance_wide_to_narrow(subtests: Subtests) -> None:
    adapter_bool = TypeAdapter(JSONPointer[bool])
    adapter_int = TypeAdapter(JSONPointer[int])
    adapter_number = TypeAdapter(JSONPointer[JSONNumber])
    adapter_value = TypeAdapter(JSONPointer[JSONValue])

    p_int = adapter_int.validate_python("/x")
    p_number = adapter_number.validate_python("/x")
    p_value = adapter_value.validate_python("/x")

    with subtests.test("int -> bool should fail"):
        with pytest.raises(InvalidJSONPointer):
            adapter_bool.validate_python(p_int)

    # It is currently only possible to enforce covariance for classes, not all TypeForms.
    # Hopefully in the future Pydantic can provide support for checking if a TypeForm is a subtype of another.

    with subtests.test(
        "jsonvalue -> bool should fail (xfail: currently there's no way to enforce covariance for TypeForms that aren't classes)"
    ):
        try:
            adapter_bool.validate_python(p_value)
        except InvalidJSONPointer:
            pass
        else:
            pytest.xfail(
                "Runtime covariance check is permissive for JSONValue -> JSONBoolean."
            )

    with subtests.test(
        "jsonnumber -> bool should fail (xfail: currently there's no way to enforce covariance for TypeForms that aren't classes)"
    ):
        try:
            adapter_bool.validate_python(p_number)
        except InvalidJSONPointer:
            pass
        else:
            pytest.xfail(
                "Runtime covariance check is permissive for JSONNumber -> JSONBoolean."
            )
