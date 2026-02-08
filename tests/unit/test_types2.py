from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Final

import pytest
from jsonpath import JSONPointer as ExtendedJsonPointer
from jsonpointer import JsonPointer as RFC6901JsonPointer
from pydantic import TypeAdapter, ValidationError
from pytest import Subtests

from jsonpatchx.backend import (
    PointerBackend,
    TargetState,
    _PointerClassProtocol,
    classify_state,
)
from jsonpatchx.exceptions import InvalidJSONPointer, PatchConflictError
from jsonpatchx.pointer import _JSONPOINTER_POINTER_BACKEND_CTX_KEY, JSONPointer
from jsonpatchx.types import JSONBoolean, JSONNumber, JSONValue
from tests.conftest import (
    AnotherIncompletePointerBackend,
    BadDotPointer,
    DotPointer,
    IncompletePointerBackend,
    PointerMissingParts,
    TypeSuite,
)

# ============================================================================
# 1) JSON alias validations
# ============================================================================


def test_json_type_validations(subtests: Subtests, suite: TypeSuite) -> None:
    """Verify that Pydantic TypeAdapters align with suite predicate logic."""
    for json_type in suite.types:
        adapter = TypeAdapter(json_type)
        pred = suite.get_predicate(json_type)

        for example in suite.examples:
            expected_ok = pred(example.value)
            label = f"{json_type!r} vs {example.label}"

            with subtests.test(label):
                if expected_ok:
                    adapter.validate_python(example.value, strict=True)
                else:
                    with pytest.raises(ValidationError):
                        adapter.validate_python(example.value, strict=True)


# ============================================================================
# 2) Pointer backend protocol checks
# ============================================================================


def test_pointer_backend(subtests: Subtests) -> None:
    with subtests.test("RFC6901JsonPointer backend"):
        assert issubclass(RFC6901JsonPointer, _PointerClassProtocol)
        assert isinstance(RFC6901JsonPointer(""), PointerBackend)
    with subtests.test("ExtendedJsonPointer backend"):
        assert issubclass(ExtendedJsonPointer, _PointerClassProtocol)
        assert isinstance(ExtendedJsonPointer(""), PointerBackend)


# ============================================================================
# 3) classify_state scenarios
# ============================================================================


@dataclass(frozen=True)
class StateScenario:
    label: str
    doc: JSONValue
    path: str
    expected: TargetState


STATE_SCENARIOS: Final[tuple[StateScenario, ...]] = (
    StateScenario("root", {"a": 1}, "", TargetState.ROOT),
    StateScenario(
        "parent-not-found", {"a": {}}, "/a/missing/b", TargetState.PARENT_NOT_FOUND
    ),
    StateScenario(
        "parent-not-container", {"a": 1}, "/a/b", TargetState.PARENT_NOT_CONTAINER
    ),
    StateScenario(
        "object-key-missing", {"a": {}}, "/a/b", TargetState.OBJECT_KEY_MISSING
    ),
    StateScenario(
        "value-present-object", {"a": {"b": 1}}, "/a/b", TargetState.VALUE_PRESENT
    ),
    StateScenario(
        "array-key-invalid", {"a": [1, 2]}, "/a/nope", TargetState.ARRAY_KEY_INVALID
    ),
    StateScenario(
        "array-index-append", {"a": [1, 2]}, "/a/-", TargetState.ARRAY_INDEX_APPEND
    ),
    StateScenario(
        "array-index-at-end", {"a": [1, 2]}, "/a/2", TargetState.ARRAY_INDEX_AT_END
    ),
    StateScenario(
        "array-index-out-of-range",
        {"a": [1, 2]},
        "/a/3",
        TargetState.ARRAY_INDEX_OUT_OF_RANGE,
    ),
    StateScenario(
        "negative-index-present",
        {"a": [1, 2]},
        "/a/-1",
        TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX,
    ),
)


@pytest.mark.parametrize(
    "scenario", STATE_SCENARIOS, ids=[s.label for s in STATE_SCENARIOS]
)
def test_classify_state(scenario: StateScenario) -> None:
    ptr = TypeAdapter(JSONPointer[JSONValue]).validate_python(scenario.path)
    assert classify_state(ptr.ptr, scenario.doc) is scenario.expected


# ============================================================================
# 4) JSONPointer type gating and method semantics
# ============================================================================


def _ptr_for(type_param: Any, path: str) -> JSONPointer[Any]:
    return TypeAdapter(JSONPointer[type_param]).validate_python(path)


def test_jsonpointer_get_is_gettable_and_is_valid_type(
    subtests: Subtests, suite: TypeSuite
) -> None:
    for type_param in suite.types:
        ptr = _ptr_for(type_param, "/k")
        for example in suite.examples:
            value = example.value
            doc: JSONValue = {"k": value}
            expected_get = suite.is_compatible(value, type_param)

            with subtests.test(f"{type_param!r} get / is_gettable ({example.label})"):
                if expected_get:
                    assert ptr.get(doc) == value
                    assert ptr.is_gettable(doc) is True
                else:
                    with pytest.raises(PatchConflictError):
                        ptr.get(doc)
                    assert ptr.is_gettable(doc) is False

            with subtests.test(f"{type_param!r} is_valid_type ({example.label})"):
                assert ptr.is_valid_type(value) is expected_get


def test_jsonpointer_remove_is_removable(subtests: Subtests, suite: TypeSuite) -> None:
    for type_param in suite.types:
        ptr = _ptr_for(type_param, "/k")
        for example in suite.examples:
            value = example.value
            doc: JSONValue = {"k": value}
            expected_remove = suite.is_compatible(value, type_param)

            with subtests.test(
                f"{type_param!r} remove / is_removable ({example.label})"
            ):
                assert ptr.is_removable(doc) is expected_remove
                if expected_remove:
                    d2 = copy.deepcopy(doc)
                    out = ptr.remove(d2)
                    assert isinstance(out, dict)
                    assert "k" not in out
                else:
                    with pytest.raises(PatchConflictError):
                        ptr.remove(copy.deepcopy(doc))


def test_jsonpointer_add_is_addable_overwrite_object(
    subtests: Subtests, suite: TypeSuite
) -> None:
    for type_param in suite.types:
        valid_examples = suite.get_examples(type_param, valid=True)
        valid_T_value = valid_examples[0].value
        alt_valid_T_value = (
            valid_examples[1].value if len(valid_examples) > 1 else valid_T_value
        )
        ptr = _ptr_for(type_param, "/k")

        for example in suite.examples:
            value = example.value
            doc: JSONValue = {"k": value}
            new_value = (
                alt_valid_T_value if value != alt_valid_T_value else valid_T_value
            )

            expected_existing_ok = suite.is_compatible(value, type_param)
            expected_new_ok = suite.is_compatible(new_value, (type_param, JSONValue))
            expected_add = expected_existing_ok and expected_new_ok

            with subtests.test(
                f"{type_param!r} add / is_addable overwrite-object ({example.label})"
            ):
                if expected_add:
                    d2 = copy.deepcopy(doc)
                    assert ptr.is_addable(d2, new_value) is True
                    out = ptr.add(d2, new_value)
                    assert isinstance(out, dict)
                    assert out["k"] == new_value
                else:
                    assert ptr.is_addable(doc, new_value) is False
                    with pytest.raises(PatchConflictError):
                        ptr.add(copy.deepcopy(doc), new_value)

            if (not expected_existing_ok) and expected_new_ok:
                with subtests.test(
                    f"{type_param!r} overwrite blocked when existing wrong type ({example.label})"
                ):
                    assert ptr.is_addable(doc, valid_T_value) is False
                    with pytest.raises(PatchConflictError):
                        ptr.add(copy.deepcopy(doc), valid_T_value)


# ============================================================================
# 5) Non-trivial pointer edge cases
# ============================================================================


def test_jsonpointer_root_semantics(subtests: Subtests) -> None:
    adapter = TypeAdapter(JSONPointer[JSONValue])

    with subtests.test("root semantics"):
        root = adapter.validate_python("")
        assert root.get({"a": 1}) == {"a": 1}
        assert root.add({"a": 1}, {"b": 2}) == {"b": 2}
        assert root.remove({"a": 1}) is None


def test_jsonpointer_array_index_handling(subtests: Subtests) -> None:
    adapter = TypeAdapter(JSONPointer[JSONValue])

    with subtests.test("get by index"):
        item = adapter.validate_python("/arr/0")
        assert item.get({"arr": [10, 20]}) == 10

    with subtests.test("append add"):
        doc = {"arr": [10]}
        appended = adapter.validate_python("/arr/-").add(doc, 30)
        assert appended["arr"] == [10, 30]

    with subtests.test("remove failures"):
        with pytest.raises(PatchConflictError):
            adapter.validate_python("/arr/-").remove({"arr": [10]})
        with pytest.raises(PatchConflictError):
            adapter.validate_python("/arr/2").remove({"arr": [10, 20]})
        with pytest.raises(PatchConflictError):
            adapter.validate_python("/arr/-1").remove({"arr": [10, 20]})
        with pytest.raises(PatchConflictError):
            adapter.validate_python("/arr/nope").remove({"arr": [10, 20]})
        with pytest.raises(PatchConflictError):
            adapter.validate_python("/arr/01").remove({"arr": [10, 20]})

    with subtests.test("insert semantics (VALUE_PRESENT)"):
        # /arr/1 with add() inserts (shifts), not overwrite
        doc = {"arr": [10, 20]}
        out = adapter.validate_python("/arr/1").add(doc, 15)
        assert out["arr"] == [10, 15, 20]


def test_jsonpointer_is_addable_edge_cases(subtests: Subtests) -> None:
    adapter = TypeAdapter(JSONPointer[JSONValue])

    with subtests.test("root is_addable"):
        root_number = TypeAdapter(JSONPointer[JSONNumber]).validate_python("")
        assert root_number.is_addable(1) is True
        assert root_number.is_addable("nope") is False

    with subtests.test("array indices"):
        doc = {"arr": [10]}
        assert adapter.validate_python("/arr/0").is_addable(doc, 5) is True
        assert adapter.validate_python("/arr/1").is_addable(doc, 5) is True
        assert adapter.validate_python("/arr/2").is_addable(doc, 5) is False
        assert adapter.validate_python("/arr/-").is_addable(doc, 5) is True
        assert adapter.validate_python("/arr/nope").is_addable(doc, 5) is False

    with subtests.test("parent not container"):
        assert adapter.validate_python("/a/b").is_addable({"a": 1}, 5) is False


def test_jsonpointer_container_type_errors(subtests: Subtests) -> None:
    adapter = TypeAdapter(JSONPointer[JSONValue])
    ptr = adapter.validate_python("/a/b")
    with subtests.test("add on primitive parent"):
        with pytest.raises(PatchConflictError):
            ptr.add({"a": 1}, "ok")
    with subtests.test("remove on primitive parent"):
        with pytest.raises(PatchConflictError):
            ptr.remove({"a": 1})


def test_jsonpointer_parent_child_edge_cases(subtests: Subtests) -> None:
    adapter = TypeAdapter(JSONPointer[JSONValue])
    parent = adapter.validate_python("/a")
    child = adapter.validate_python("/a/b")
    same = adapter.validate_python("/a")
    with subtests.test("parent/child basics"):
        assert parent.is_parent_of(child) is True
        assert child.is_child_of(parent) is True
        assert parent.is_parent_of(same) is False
        assert parent.is_child_of(child) is False

    with subtests.test("backend mismatch errors"):
        dot_adapter = TypeAdapter(JSONPointer[JSONValue, DotPointer])
        dot_ptr = dot_adapter.validate_python("a.b")
        with pytest.raises(InvalidJSONPointer):
            parent.is_parent_of(dot_ptr)
        with pytest.raises(InvalidJSONPointer):
            parent.is_child_of(dot_ptr)


# ============================================================================
# 6+) Everything else
# ============================================================================


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
        assert ptr.is_root(doc) is False
        root = adapter.validate_python("")
        assert root.is_root(doc) is True
        missing = adapter.validate_python(missing_path)
        assert missing.is_root(doc) is False

    with subtests.test("is_parent_of"):
        assert parent.is_parent_of(ptr) is True
        assert ptr.is_parent_of(parent) is False
        if pointer_cls is None:
            with pytest.raises(InvalidJSONPointer):
                ptr.is_parent_of(DotPointer("a.b"))
        else:
            with pytest.raises(InvalidJSONPointer):
                ptr.is_parent_of(RFC6901JsonPointer("/a/b"))

    with subtests.test("is_child_of"):
        assert child.is_child_of(ptr) is True
        assert ptr.is_child_of(child) is False
        assert ptr.is_child_of(ptr) is False
        if pointer_cls is None:
            with pytest.raises(InvalidJSONPointer):
                ptr.is_child_of(DotPointer("a.b"))
        else:
            with pytest.raises(InvalidJSONPointer):
                ptr.is_child_of(RFC6901JsonPointer("/a/b"))

    with subtests.test("is_valid_type"):
        bool_ptr = bool_adapter.validate_python(parent_path)
        assert bool_ptr.is_valid_type(True) is True
        assert bool_ptr.is_valid_type(1) is False

    with subtests.test("get"):
        assert ptr.get(doc) == 1

    with subtests.test("is_gettable"):
        assert ptr.is_gettable(doc) is True
        missing = adapter.validate_python(missing_path)
        assert missing.is_gettable(doc) is False

    with subtests.test("is_removable"):
        assert ptr.is_removable(doc) is True
        missing = adapter.validate_python(missing_path)
        assert missing.is_removable(doc) is False

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
            else {_JSONPOINTER_POINTER_BACKEND_CTX_KEY: registry_backend}
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


def test_jsonpointer_backend_reuse(subtests: Subtests) -> None:
    dot_ptr_adapter = TypeAdapter(JSONPointer[JSONValue, DotPointer])
    ptr1a = dot_ptr_adapter.validate_python("a.b")
    ptr1b = dot_ptr_adapter.validate_python(ptr1a)
    ptr2a = dot_ptr_adapter.validate_python(DotPointer("a.b"))
    ptr2b = dot_ptr_adapter.validate_python(ptr2a)

    class DotPointerSubclass(DotPointer):
        pass

    ptr3a = dot_ptr_adapter.validate_python(DotPointerSubclass("c.d"))
    ptr3b = dot_ptr_adapter.validate_python(ptr3a)

    with subtests.test("reuse compatible backend instances"):
        assert ptr1a.ptr is ptr1b.ptr
        assert ptr2a.ptr is ptr2b.ptr
        assert ptr3a.ptr is ptr3b.ptr

    narrower_dot_ptr_adapter = TypeAdapter(JSONPointer[JSONValue, DotPointerSubclass])

    with subtests.test("don't coerce backend superclass instances"):
        with pytest.raises(InvalidJSONPointer):
            narrower_dot_ptr_adapter.validate_python(DotPointer("e.f"))

    with subtests.test("reject incompatible backend instances"):
        with pytest.raises(InvalidJSONPointer):
            dot_ptr_adapter.validate_python(RFC6901JsonPointer("/hello"))


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
            PointerMissingParts,
            BadDotPointer,
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

    with subtests.test("reject invalid default backend string syntax"):
        adapter = TypeAdapter(JSONPointer[JSONValue])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("a.b")

    with subtests.test("reject invalid custom backend string syntax"):
        adapter = TypeAdapter(JSONPointer[JSONValue, DotPointer])
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python("a..b")


def test_jsonpointer_path_validation(subtests: Subtests) -> None:
    adapter = TypeAdapter(JSONPointer[JSONValue, DotPointer])
    with subtests.test("accept strings"):
        adapter.validate_python("a.b")
    with subtests.test("accept compatible PointerBackend instances"):
        adapter.validate_python(DotPointer("a.b"))
    with subtests.test("accept other JSONPointers"):
        ptr = adapter.validate_python("a.b")
        adapter.validate_python(ptr)
    with subtests.test("reject incompatible PointerBackends"):
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python(RFC6901JsonPointer("/hello"))
        with pytest.raises(InvalidJSONPointer):
            adapter.validate_python(ExtendedJsonPointer("/hello"))
    with subtests.test("accepts narrower PointerBackends"):

        class DotPointerSubclass(DotPointer):
            pass

        adapter.validate_python(DotPointerSubclass("a.b"))


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
