from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter
from typing import Final

import pytest
from jsonpath import JSONPointer as ExtendedJsonPointer
from jsonpointer import JsonPointer as CustomJsonPointer
from pytest import Subtests

from jsonpatchx.backend import (
    DEFAULT_POINTER_CLS,
    DEFAULT_SELECTOR_CLS,
    PointerBackend,
    SelectorBackend,
    TargetState,
    classify_state,
)
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.types import JSONValue
from tests.support.selectors import SimpleSelector


def test_pointer_backend(subtests: Subtests) -> None:
    with subtests.test("built-in RFC 6901 backend"):
        assert isinstance(DEFAULT_POINTER_CLS("/a"), PointerBackend)

    with subtests.test("Custom JsonPointer backend"):
        assert isinstance(CustomJsonPointer(""), PointerBackend)
    with subtests.test("Extended JsonPointer backend"):
        assert isinstance(ExtendedJsonPointer(""), PointerBackend)


def test_selector_backend(subtests: Subtests) -> None:
    with subtests.test("built-in RFC 9535 backend"):
        assert isinstance(DEFAULT_SELECTOR_CLS("$.a"), SelectorBackend)

    with subtests.test("simple selector backend"):
        assert isinstance(SimpleSelector("a"), SelectorBackend)


def test_selector_backend_pointers(subtests: Subtests) -> None:
    cases = [
        ("built-in RFC 9535 backend", DEFAULT_SELECTOR_CLS("$.a"), {"a": 1}),
        ("simple selector backend", SimpleSelector("a"), {"a": 1}),
    ]

    for label, selector, doc in cases:
        with subtests.test(label):
            pointers = list(selector.pointers(doc))
            assert len(pointers) == 1
            assert isinstance(pointers[0], PointerBackend)
            assert str(pointers[0]) == "/a"


def test_default_backend_string_representations(subtests: Subtests) -> None:
    with subtests.test("built-in RFC 6901 pointer backend"):
        pointer = DEFAULT_POINTER_CLS("/a")
        assert str(pointer) == "/a"
        assert repr(pointer) == "JsonPointerRFC6901('/a')"

    with subtests.test("built-in RFC 9535 selector backend"):
        selector = DEFAULT_SELECTOR_CLS("$.a")
        assert str(selector) == "$.a"
        assert repr(selector) == "JsonPathRFC9535('$.a')"


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
assert len(STATE_SCENARIOS) == len(TargetState), "STATE_SCENARIOS not set up correctly"


@pytest.mark.parametrize("scenario", STATE_SCENARIOS, ids=attrgetter("label"))
def test_classify_state(scenario: StateScenario) -> None:
    ptr = JSONPointer.parse(scenario.path)
    assert classify_state(ptr.ptr, scenario.doc) is scenario.expected
