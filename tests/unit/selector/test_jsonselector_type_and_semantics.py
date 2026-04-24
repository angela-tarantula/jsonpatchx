from __future__ import annotations

import copy
from functools import partial
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import TypeAdapter
from pydantic.experimental.missing_sentinel import MISSING
from pytest import Subtests

from jsonpatchx.backend import _DEFAULT_SELECTOR_CLS, SelectorBackend
from jsonpatchx.exceptions import InvalidJSONSelector, PatchConflictError
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.selector import JSONSelector
from jsonpatchx.types import JSONNumber, JSONValue
from tests.support.selectors import SimpleSelector
from tests.support.type_suite import TypeSuite


def test_jsonselector_getall(subtests: Subtests, suite: TypeSuite) -> None:
    for type_param in suite.types:
        selector = JSONSelector.parse("$.items[*]", type_param=type_param)
        for example in suite.examples:
            value = example.value
            doc: Any = {"items": [value]}
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


def test_jsonselector_removeall(subtests: Subtests, suite: TypeSuite) -> None:
    for type_param in suite.types:
        selector = JSONSelector.parse("$.record.*", type_param=type_param)
        for example in suite.examples:
            value = example.value
            doc: Any = {"record": {"a": value, "b": value}}
            expected_remove = suite.is_compatible(value, type_param)

            with subtests.test(
                f"{type_param!r} removeall / is_removable ({example.label})"
            ):
                if expected_remove:
                    assert selector.is_removable(doc) is True
                    d2 = copy.deepcopy(doc)
                    out = selector.removeall(d2)
                    assert isinstance(out, dict)
                    assert out == {"record": {}}
                    assert selector.getall(d2) == []
                else:
                    assert selector.is_removable(doc) is False
                    with pytest.raises(PatchConflictError):
                        selector.removeall(copy.deepcopy(doc))


def test_jsonselector_addall(subtests: Subtests, suite: TypeSuite) -> None:
    for type_param in suite.types:
        valid_examples = suite.get_examples(type_param, valid=True)
        valid_T_value = valid_examples[0].value
        alt_valid_T_value = valid_examples[1].value
        selector = JSONSelector.parse("$.record.*", type_param=type_param)

        for example in suite.examples:
            value = example.value
            doc: Any = {"record": {"a": value, "b": value}}
            new_value = alt_valid_T_value

            expected_existing_ok = suite.is_compatible(value, type_param)
            expected_new_ok = suite.is_compatible(new_value, (type_param, JSONValue))
            expected_add = expected_existing_ok and expected_new_ok

            with subtests.test(
                f"{type_param!r} addall / is_addable overwrite-object ({example.label})"
            ):
                if expected_add:
                    d2 = copy.deepcopy(doc)
                    assert selector.is_addable(d2, new_value) is True
                    out = selector.addall(d2, new_value)
                    assert isinstance(out, dict)
                    assert out == {"record": {"a": new_value, "b": new_value}}
                else:
                    assert selector.is_addable(doc, new_value) is False
                    with pytest.raises(PatchConflictError):
                        selector.addall(copy.deepcopy(doc), new_value)

            if (not expected_existing_ok) and expected_new_ok:
                with subtests.test(
                    f"{type_param!r} overwrite blocked when existing wrong type ({example.label})"
                ):
                    assert selector.is_addable(doc, valid_T_value) is False
                    with pytest.raises(PatchConflictError):
                        selector.addall(copy.deepcopy(doc), valid_T_value)


def test_jsonselector_root_semantics() -> None:
    selector: JSONSelector[JSONValue] = JSONSelector.parse("$")
    assert selector.getall({"a": 1}) == [{"a": 1}]
    assert selector.get_pointers({"a": 1}) == [JSONPointer.parse("")]
    assert selector.addall({"a": 1}, {"b": 2}) == {"b": 2}
    assert selector.removeall({"a": 1}) is MISSING


def test_default_jsonselector_zero_matches() -> None:
    missing: JSONSelector[JSONValue] = JSONSelector.parse("$.missing[*]")
    assert missing.getall({"a": 1}) == []
    assert missing.get_pointers({"a": 1}) == []
    assert missing.is_gettable({"a": 1}) is True
    assert missing.is_addable({"a": 1}, 1) is True
    assert missing.is_addable({"a": 1}, object()) is False
    assert missing.is_removable({"a": 1}) is True
    assert missing.addall({"a": 1}, 1) == {"a": 1}
    assert missing.removeall({"a": 1}) == {"a": 1}


@pytest.mark.parametrize(
    ("custom_selector_cls", "selector_str", "missing_str", "wrong_type_str", "doc"),
    [
        (
            None,
            "$.record.*",
            "$.missing[*]",
            "$.bool",
            {"record": {"number_a": 1, "number_b": 2}, "bool": True},
        ),
        (
            SimpleSelector,
            "record_values",
            "missing",
            "a",
            {"record": {"a": 1, "b": 2}, "a": True},
        ),
    ],
)
def test_jsonselector_public_methods_are_backend_agnostic(
    subtests: Subtests,
    custom_selector_cls: type[SimpleSelector] | None,
    selector_str: str,
    missing_str: str,
    wrong_type_str: str,
    doc: JSONValue,
) -> None:
    if custom_selector_cls is None:
        parse = JSONSelector.parse
    else:
        parse = partial(JSONSelector.parse, backend=custom_selector_cls)

    selector = parse(selector_str, type_param=JSONNumber)
    missing = parse(missing_str, type_param=JSONNumber)
    wrong_type = parse(wrong_type_str, type_param=JSONNumber)

    with subtests.test("ptr"):
        assert selector.ptr is not None

    with subtests.test("type_param"):
        assert selector.type_param is JSONNumber

    with subtests.test("is_valid_type"):
        assert selector.is_valid_type(1) is True
        assert selector.is_valid_type(True) is False

    with subtests.test("getall"):
        assert selector.getall(doc) == [1, 2]

    with subtests.test("get_pointers"):
        expected_pointers = (
            ["/record/number_a", "/record/number_b"]
            if custom_selector_cls is None
            else ["/record/a", "/record/b"]
        )
        assert [
            str(pointer) for pointer in selector.get_pointers(doc)
        ] == expected_pointers

    with subtests.test("is_gettable"):
        assert selector.is_gettable(doc) is True
        assert missing.is_gettable(doc) is True

    with subtests.test("is_addable"):
        assert selector.is_addable(copy.deepcopy(doc)) is True
        assert selector.is_addable(copy.deepcopy(doc), 9) is True
        assert selector.is_addable(copy.deepcopy(doc), object()) is False
        assert wrong_type.is_addable(copy.deepcopy(doc)) is False
        assert missing.is_addable(copy.deepcopy(doc), 9) is True

    with subtests.test("addall"):
        expected_added = (
            {"record": {"number_a": 9, "number_b": 9}, "bool": True}
            if custom_selector_cls is None
            else {"record": {"a": 9, "b": 9}, "a": True}
        )
        assert selector.addall(copy.deepcopy(doc), 9) == expected_added

    with subtests.test("is_removable"):
        assert selector.is_removable(doc) is True
        assert missing.is_removable(doc) is True

    with subtests.test("removeall"):
        expected_removed = (
            {"record": {}, "bool": True}
            if custom_selector_cls is None
            else {"record": {}, "a": True}
        )
        assert selector.removeall(copy.deepcopy(doc)) == expected_removed

    with subtests.test("__str__"):
        assert str(selector) == selector_str


def test_default_jsonselector_invalid_matches_from_backend_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenBackend:
        def finditer(self, _doc: JSONValue) -> list[object]:
            return [object()]

    bad_match: JSONSelector[JSONValue] = JSONSelector.parse("$.a")
    monkeypatch.setattr(bad_match, "_selector", BrokenBackend())

    with pytest.raises(InvalidJSONSelector):
        bad_match.getall({"a": 1})


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


def test_selector_backend_binding(subtests: Subtests) -> None:
    class BoundSelector(SimpleSelector):
        pass

    if TYPE_CHECKING:
        _dont_raise_mypy_error_1: SelectorBackend = _DEFAULT_SELECTOR_CLS("")

    with subtests.test("no backends"):
        selector = JSONSelector.parse("$.a", backend=None)
        assert isinstance(selector.ptr, _DEFAULT_SELECTOR_CLS)

    with subtests.test("bound backend"):
        selector = JSONSelector.parse("a", backend=BoundSelector)
        assert isinstance(selector.ptr, BoundSelector)

    with subtests.test("explicit default backend class behaves like omitted backend"):
        selector = JSONSelector.parse("$.a", backend=_DEFAULT_SELECTOR_CLS)
        assert isinstance(selector.ptr, _DEFAULT_SELECTOR_CLS)

    with subtests.test("bound SelectorBackend is invalid"):
        with pytest.raises(InvalidJSONSelector):
            JSONSelector.parse("$.a", backend=SelectorBackend)


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


def test_default_jsonselector_returns_rfc6901_compliant_pointers(
    subtests: Subtests,
) -> None:
    """
    Guard the built-in backend's exported-pointer behavior, not just matching.

    JsonPatchX's default selector backend delegates JSONPath evaluation to
    ``python-jsonpath``, but JsonPatchX does more than ask upstream for matched
    values. It also asks each upstream match for its exact location and then
    uses that location for later pointer-based reads and mutations.

    That means the shipped selector contract depends on both:

    - upstream JSONPath matching
    - the safety of the pointers attached to those matches

    Upstream ``python-jsonpath`` matching can still be correct while its own
    ``JSONPointer`` helper remains non-compliant in ways that cause retargeting.
    If JsonPatchX trusted ``match.pointer()`` directly, these cases would stop
    pointing at literal ``"#..."`` object keys and would instead resolve to
    unintended targets. That is why the default backend rebuilds pointers from
    ``match.parts`` and re-exports them through JsonPatchX's RFC 6901 pointer
    backend instead of leaking upstream pointer objects. See
    ``_DEFAULT_SELECTOR_CLS.finditer()`` in ``jsonpatchx.backend``: that method
    intentionally rebuilds exported pointers from ``match.parts`` rather than
    trusting upstream ``match.pointer()``.
    """

    cases = [
        ("hash-key", "$['#arr']", {"#arr": "hit"}, {"arr": 123}),
        ("hash-index", "$['arr']['#1']", {"arr": {"#1": "hit"}}, {"arr": [10, 20]}),
    ]

    for label, selector_str, matched_doc, retarget_doc in cases:
        with subtests.test(label):
            selector: JSONSelector[JSONValue] = JSONSelector.parse(selector_str)
            [pointer] = selector.get_pointers(matched_doc)

            assert pointer.get(matched_doc) == "hit"
            with pytest.raises(PatchConflictError):
                pointer.get(retarget_doc)
