from __future__ import annotations

from typing import Any

import pytest
from pydantic import TypeAdapter
from pytest import Subtests

from jsonpatchx.exceptions import InvalidJSONSelector, PatchConflictError
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.selector import JSONSelector
from jsonpatchx.types import JSONNumber, JSONValue
from tests.support.selectors import SimpleSelector
from tests.support.type_suite import TypeSuite


def test_jsonselector_getall(subtests: Subtests, suite: TypeSuite) -> None:
    for type_param in suite.types:
        selector: Any = JSONSelector.parse(
            "all_items",
            type_param=type_param,
            backend=SimpleSelector,
        )
        for example in suite.examples:
            value = example.value
            doc: JSONValue = {"items": [value]}
            expected_get = suite.is_compatible(value, type_param)

            with subtests.test(
                f"{type_param!r} getall / is_gettable ({example.label})"
            ):
                if expected_get:
                    assert selector.getall(doc) == [value]
                    assert selector.is_gettable(doc) is True
                else:
                    with pytest.raises(PatchConflictError):
                        selector.getall(doc)
                    assert selector.is_gettable(doc) is False

            with subtests.test(f"{type_param!r} is_valid_type ({example.label})"):
                assert selector.is_valid_type(value) is expected_get


def test_jsonselector_addall_and_removeall_with_custom_backend() -> None:
    selector: JSONSelector[JSONNumber, SimpleSelector] = JSONSelector.parse(
        "record_values",
        type_param=JSONNumber,
        backend=SimpleSelector,
    )

    assert selector.addall({"record": {"a": 1, "b": 2}}, 9) == {
        "record": {"a": 9, "b": 9}
    }
    assert selector.removeall({"record": {"a": 1, "b": 2}}) == {"record": {}}


def test_jsonselector_root_semantics_with_custom_backend() -> None:
    selector: JSONSelector[JSONValue, SimpleSelector] = JSONSelector.parse(
        "root", backend=SimpleSelector
    )
    assert selector.getall({"a": 1}) == [{"a": 1}]
    assert selector.get_pointers({"a": 1}) == [JSONPointer.parse("")]
    assert selector.addall({"a": 1}, {"b": 2}) == {"b": 2}


def test_jsonselector_zero_matches_and_invalid_matches() -> None:
    missing: JSONSelector[JSONValue, SimpleSelector] = JSONSelector.parse(
        "missing", backend=SimpleSelector
    )
    assert missing.getall({"a": 1}) == []
    assert missing.get_pointers({"a": 1}) == []
    assert missing.is_gettable({"a": 1}) is True
    assert missing.is_addable({"a": 1}, 1) is True
    assert missing.is_addable({"a": 1}, object()) is False
    assert missing.is_removable({"a": 1}) is True
    assert missing.addall({"a": 1}, 1) == {"a": 1}
    assert missing.removeall({"a": 1}) == {"a": 1}

    bad_match: JSONSelector[JSONValue, SimpleSelector] = JSONSelector.parse(
        "bad_match", backend=SimpleSelector
    )
    with pytest.raises(InvalidJSONSelector):
        bad_match.getall({"a": 1})


def test_jsonselector_is_addable_without_value_uses_pointer_semantics() -> None:
    selector: JSONSelector[JSONNumber, SimpleSelector] = JSONSelector.parse(
        "a",
        type_param=JSONNumber,
        backend=SimpleSelector,
    )

    assert selector.is_addable({"a": 1}) is True
    assert selector.is_addable({"a": "nope"}) is False


def test_jsonselector_applies_matches_sequentially_in_backend_order() -> None:
    selector: JSONSelector[JSONValue, SimpleSelector] = JSONSelector.parse(
        "root_and_a", backend=SimpleSelector
    )
    doc: JSONValue = {"a": {"b": 1}}
    assert selector.is_addable(doc, {"replaced": True}) is True
    assert selector.is_removable(doc) is True

    assert selector.addall(doc, {"replaced": True}) == {
        "replaced": True,
        "a": {"replaced": True},
    }
    with pytest.raises(PatchConflictError):
        selector.removeall({"a": {"b": 1}})


@pytest.mark.xfail(
    reason="removeall() still uses backend order instead of a safety-maximizing order",
    strict=False,
)
def test_jsonselector_removeall_future_can_reorder_safe_removes() -> None:
    selector: JSONSelector[JSONValue, SimpleSelector] = JSONSelector.parse(
        "items_0_1", backend=SimpleSelector
    )
    doc: JSONValue = {"items": [1, 2]}

    assert selector.is_removable(doc) is True
    assert selector.removeall(doc) == {"items": []}


@pytest.mark.xfail(
    reason="is_removable() currently uses the loose existential MVP contract",
    strict=False,
)
def test_jsonselector_is_removable_future_rejects_duplicate_matches() -> None:
    selector: JSONSelector[JSONValue, SimpleSelector] = JSONSelector.parse(
        "double_a", backend=SimpleSelector
    )

    assert selector.is_removable({"a": 1}) is False


def test_jsonselector_backend_reuse_and_mismatch() -> None:
    original: JSONSelector[JSONValue, SimpleSelector] = JSONSelector.parse(
        "a", backend=SimpleSelector
    )
    reparsed: JSONSelector[JSONValue, SimpleSelector] = JSONSelector.parse(
        original, backend=SimpleSelector
    )
    default_reparsed: JSONSelector[JSONValue] = JSONSelector.parse(original)
    raw_backend = SimpleSelector("a")

    assert reparsed.ptr is original.ptr
    assert default_reparsed.ptr is original.ptr

    with pytest.raises(InvalidJSONSelector):
        JSONSelector.parse(raw_backend)


def test_jsonselector_json_schema() -> None:
    default_schema = TypeAdapter(JSONSelector[JSONNumber]).json_schema()
    assert default_schema["type"] == "string"
    assert default_schema["format"] == "json-path"
    assert default_schema["x-selector-type-schema"] == {"type": "number"}

    custom_schema = TypeAdapter(JSONSelector[JSONValue, SimpleSelector]).json_schema()
    assert custom_schema["format"] == "x-json-selector"
    assert custom_schema["x-selector-type-schema"] == {}


def test_default_jsonselector_backend_smoke() -> None:
    selector: JSONSelector[JSONNumber] = JSONSelector.parse(
        "$.items[*]", type_param=JSONNumber
    )
    assert selector.getall({"items": [1, 2]}) == [1, 2]
    assert [str(pointer) for pointer in selector.get_pointers({"items": [1, 2]})] == [
        "/items/0",
        "/items/1",
    ]
