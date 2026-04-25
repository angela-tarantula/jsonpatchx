from __future__ import annotations

import copy
from functools import partial
from typing import TYPE_CHECKING, Any, Generic, cast

import pytest
from pydantic import BaseModel, TypeAdapter
from pydantic_core import MISSING
from pytest import Subtests
from typing_extensions import TypeVar

from jsonpatchx.backend import DEFAULT_SELECTOR_CLS, SelectorBackend
from jsonpatchx.exceptions import (
    InvalidJSONSelector,
    PatchConflictError,
)
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.selector import JSONSelector
from jsonpatchx.types import JSONBoolean, JSONNumber, JSONValue
from tests.support.selectors import (
    AnotherIncompleteSelectorBackend,
    BadSimpleSelector,
    IncompleteSelectorBackend,
    SelectorMissingPointers,
    SimpleSelector,
)
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


def test_jsonselector_root_semantics(subtests: Subtests) -> None:
    selector: JSONSelector[JSONValue] = JSONSelector.parse("$")

    with subtests.test("root selector with existing document"):
        doc: JSONValue = {"a": 1}
        assert selector.getall(doc) == [doc]
        assert selector.get_pointers(doc) == [JSONPointer.parse("")]
        assert selector.is_gettable(doc) is True
        assert selector.is_removable(doc) is True
        assert selector.is_addable(doc, {"b": 2}) is True
        assert selector.addall(copy.deepcopy(doc), {"b": 2}) == {"b": 2}
        assert selector.removeall(copy.deepcopy(doc)) is MISSING

    with subtests.test("root selector with missing document"):
        doc: JSONValue = cast(JSONValue, MISSING)
        with pytest.raises(PatchConflictError):
            selector.getall(doc)
        assert selector.get_pointers(doc) == [JSONPointer.parse("")]
        assert selector.is_gettable(doc) is False
        assert selector.is_removable(doc) is False
        assert selector.is_addable(doc, {"b": 2}) is True
        assert selector.addall(doc, {"b": 2}) == {"b": 2}
        with pytest.raises(PatchConflictError):
            selector.removeall(doc)


@pytest.mark.xfail(
    reason="JSON helper types still accept the Pydantic MISSING sentinel at validation time",
    strict=True,
)
def test_jsonselector_is_valid_type_rejects_missing_for_narrowed_types() -> None:
    selector = JSONSelector.parse("$.flag", type_param=JSONBoolean)

    assert selector.is_valid_type(MISSING) is False


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


def test_default_jsonselector_backend_corruption_paths(
    subtests: Subtests,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with subtests.test(
        "resolution failure raises in accessors/mutators and returns False from boolean helpers"
    ):
        selector = JSONSelector.parse("a.b", backend=SimpleSelector)
        with pytest.raises(PatchConflictError):
            selector.get_pointers({"a": 1})
        with pytest.raises(PatchConflictError):
            selector.getall({"a": 1})
        with pytest.raises(PatchConflictError):
            selector.addall({"a": 1}, 1)
        with pytest.raises(PatchConflictError):
            selector.removeall({"a": 1})
        assert selector.is_gettable({"a": 1}) is False
        assert selector.is_addable({"a": 1}) is False
        assert selector.is_addable({"a": 1}, 1) is False
        assert selector.is_removable({"a": 1}) is False

    with subtests.test(
        "invalid backend pointer raises in accessors and returns False in boolean helpers"
    ):

        class InvalidPointerBackend:
            def pointers(self, _doc: JSONValue) -> list[object]:
                return [object()]

        selector: JSONSelector[JSONValue] = JSONSelector.parse("$.a")
        monkeypatch.setattr(selector, "_selector", InvalidPointerBackend())
        with pytest.raises(InvalidJSONSelector):
            selector.get_pointers({"a": 1})
        with pytest.raises(InvalidJSONSelector):
            selector.getall({"a": 1})
        with pytest.raises(InvalidJSONSelector):
            selector.addall({"a": 1}, 1)
        with pytest.raises(InvalidJSONSelector):
            selector.removeall({"a": 1})
        assert selector.is_gettable({"a": 1}) is False
        assert selector.is_addable({"a": 1}) is False
        assert selector.is_addable({"a": 1}, 1) is False
        assert selector.is_removable({"a": 1}) is False


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
        _dont_raise_mypy_error_1: SelectorBackend = DEFAULT_SELECTOR_CLS("")

    with subtests.test("no backends"):
        selector = JSONSelector.parse("$.a", backend=None)
        assert isinstance(selector.ptr, DEFAULT_SELECTOR_CLS)

    with subtests.test("bound backend"):
        selector = JSONSelector.parse("a", backend=BoundSelector)
        assert isinstance(selector.ptr, BoundSelector)

    with subtests.test("explicit default backend class behaves like omitted backend"):
        selector = JSONSelector.parse("$.a", backend=DEFAULT_SELECTOR_CLS)
        assert isinstance(selector.ptr, DEFAULT_SELECTOR_CLS)

    with subtests.test("bound SelectorBackend is invalid"):
        with pytest.raises(InvalidJSONSelector):
            JSONSelector.parse("$.a", backend=SelectorBackend)


def test_jsonselector_backend_reuse(subtests: Subtests) -> None:
    class SimpleSelectorSubclass(SimpleSelector):
        pass

    selector1a = JSONSelector.parse("a", backend=SimpleSelector)
    selector1b = JSONSelector.parse(selector1a, backend=SimpleSelector)
    selector1c = JSONSelector.parse(selector1a)
    raw_selector = SimpleSelector("a")
    selector2a = JSONSelector.parse(raw_selector, backend=SimpleSelector)
    selector2b = JSONSelector.parse(selector2a, backend=SimpleSelector)
    selector3a = JSONSelector.parse(SimpleSelectorSubclass("a"), backend=SimpleSelector)
    selector3b = JSONSelector.parse(selector3a, backend=SimpleSelector)

    with subtests.test("reuse compatible backend instances"):
        assert selector1a.ptr is selector1b.ptr
        assert selector1a.ptr is selector1c.ptr
        assert selector2a.ptr is raw_selector
        assert selector2a.ptr is selector2b.ptr
        assert selector3a.ptr is selector3b.ptr

    with subtests.test("don't coerce backend superclass instances"):
        with pytest.raises(InvalidJSONSelector):
            JSONSelector.parse(SimpleSelector("a"), backend=SimpleSelectorSubclass)

    with subtests.test(
        "reject raw backend instances when omitted backend defaults to RFC 9535"
    ):
        with pytest.raises(InvalidJSONSelector):
            JSONSelector.parse(SimpleSelector("a"))

    with subtests.test("reject incompatible backend instances"):
        with pytest.raises(InvalidJSONSelector):
            JSONSelector.parse(DEFAULT_SELECTOR_CLS("$.a"), backend=SimpleSelector)

    with subtests.test(
        "reparse JSONSelector into different but compatible-syntax backend"
    ):
        reparsed = JSONSelector.parse(selector1a, backend=SimpleSelectorSubclass)
        assert isinstance(reparsed.ptr, SimpleSelectorSubclass)
        assert reparsed.ptr is not selector1a.ptr


def test_jsonselector_type_args_validation(subtests: Subtests) -> None:
    with subtests.test("invalid type param"):
        with pytest.raises(InvalidJSONSelector):
            TypeAdapter(JSONSelector[int()])

    with subtests.test("not enough args"):
        with pytest.raises(TypeError):
            TypeAdapter(JSONSelector)

    with subtests.test("too many args"):
        with pytest.raises(TypeError):
            TypeAdapter(JSONSelector[JSONValue, SimpleSelector, int])

    with subtests.test("invalid backend"):
        for invalid_backend in [
            object,
            object(),
            JSONValue,
            str,
            IncompleteSelectorBackend,
            AnotherIncompleteSelectorBackend,
            SelectorMissingPointers,
            SelectorBackend,
            BadSimpleSelector,
            SimpleSelector("a"),
            "SimpleSelector",
        ]:
            with pytest.raises(InvalidJSONSelector):
                adapter = TypeAdapter(JSONSelector[JSONValue, invalid_backend])
                adapter.validate_python("a")

    with subtests.test("valid backend"):
        default_adapter = TypeAdapter(JSONSelector[JSONValue, DEFAULT_SELECTOR_CLS])
        default_adapter.validate_python("$.a")

        custom_adapter = TypeAdapter(JSONSelector[JSONValue, SimpleSelector])
        custom_adapter.validate_python("a")

    with subtests.test(
        "backend typevar bound to SelectorBackend requires specialization or default"
    ):
        S_backend = TypeVar("S_backend", bound=SelectorBackend)
        adapter = TypeAdapter(JSONSelector[JSONValue, S_backend])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("$.a")

    with subtests.test("backend typevar constraints require specialization or default"):
        S_constrained = TypeVar("S_constrained", SimpleSelector, DEFAULT_SELECTOR_CLS)
        adapter = TypeAdapter(JSONSelector[JSONValue, S_constrained])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("$.a")

    with subtests.test("backend typevar non-backend bound fails at runtime"):
        S_invalid_bound = TypeVar("S_invalid_bound", bound=str)
        adapter = TypeAdapter(JSONSelector[JSONValue, S_invalid_bound])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("$.a")

    with subtests.test("backend typevar without constraints or bound is rejected"):
        S_unbound = TypeVar("S_unbound")
        adapter = TypeAdapter(JSONSelector[JSONValue, S_unbound])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("$.a")

    with subtests.test("backend typevar default is honored at runtime"):

        class DefaultSimpleSelector(SimpleSelector):
            pass

        S_default = TypeVar(
            "S_default", bound=SelectorBackend, default=DefaultSimpleSelector
        )
        adapter = TypeAdapter(JSONSelector[JSONValue, S_default])
        selector = adapter.validate_python("a")
        assert isinstance(selector.ptr, DefaultSimpleSelector)

    with subtests.test("backend typevar nested default typevar is resolved"):
        S_inner = TypeVar("S_inner", bound=SelectorBackend, default=SimpleSelector)
        S_outer = TypeVar("S_outer", bound=SelectorBackend, default=S_inner)
        adapter = TypeAdapter(JSONSelector[JSONValue, S_outer])
        selector = adapter.validate_python("a")
        assert isinstance(selector.ptr, SimpleSelector)

    with subtests.test("backend typevar non-type default is rejected"):
        S_non_type_default = TypeVar(
            "S_non_type_default", bound=SelectorBackend, default=123
        )
        adapter = TypeAdapter(JSONSelector[JSONValue, S_non_type_default])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("$.a")

    with subtests.test("backend typevar SelectorBackend default is rejected"):
        S_protocol_default = TypeVar(
            "S_protocol_default", bound=SelectorBackend, default=SelectorBackend
        )
        adapter = TypeAdapter(JSONSelector[JSONValue, S_protocol_default])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("$.a")

    with subtests.test("TypeVar without default works in Python 3.12 and below"):
        import typing

        S_backend = typing.TypeVar("S_backend", bound=SelectorBackend)
        adapter = TypeAdapter(JSONSelector[JSONValue, S_backend])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("$.a")

    with subtests.test("reject invalid default backend string syntax"):
        adapter = TypeAdapter(JSONSelector[JSONValue])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("a")

    with subtests.test("reject invalid custom backend string syntax"):
        adapter = TypeAdapter(JSONSelector[JSONValue, SimpleSelector])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("$.a")


def test_selector_backend_typevar_explicit_policy_cases(subtests: Subtests) -> None:
    with subtests.test("explicit SelectorBackend parameter is rejected at runtime"):
        adapter = TypeAdapter(JSONSelector[JSONValue, SelectorBackend])
        with pytest.raises(InvalidJSONSelector):
            adapter.validate_python("$.a")

    with subtests.test("direct specialization uses explicit backend"):

        class OtherSimpleSelector(SimpleSelector):
            pass

        S_backend = TypeVar("S_backend", bound=SelectorBackend, default=SimpleSelector)

        class GenericModel(BaseModel, Generic[S_backend]):
            path: JSONSelector[JSONValue, S_backend]

        model = GenericModel[OtherSimpleSelector].model_validate({"path": "a"})
        assert isinstance(model.path.ptr, OtherSimpleSelector)


def test_jsonselector_json_schema_backend_resolution(subtests: Subtests) -> None:
    with subtests.test("default backend reports json-path format"):
        schema = TypeAdapter(JSONSelector[JSONValue]).json_schema()
        assert schema["type"] == "string"
        assert schema["format"] == "json-path"
        assert schema["x-selector-type-schema"] == {}

    with subtests.test("concrete custom backend reports custom format"):
        schema = TypeAdapter(JSONSelector[JSONNumber, SimpleSelector]).json_schema()
        assert schema["type"] == "string"
        assert schema["format"] == "x-json-selector"
        assert schema["x-selector-type-schema"] == {"type": "number"}

    with subtests.test("backend TypeVar without default cannot produce JSON schema"):
        S_backend = TypeVar("S_backend", bound=SelectorBackend)
        with pytest.raises(InvalidJSONSelector):
            TypeAdapter(JSONSelector[JSONValue, S_backend]).json_schema()

    with subtests.test(
        "backend TypeVar defaulting to built-in backend reports json-path format"
    ):
        S_default_default_selector = TypeVar(
            "S_default_default_selector",
            bound=SelectorBackend,
            default=DEFAULT_SELECTOR_CLS,
        )
        schema = TypeAdapter(
            JSONSelector[JSONValue, S_default_default_selector]
        ).json_schema()
        assert schema["format"] == "json-path"

    with subtests.test(
        "backend TypeVar defaulting to custom backend reports custom format"
    ):
        S_default_custom_selector = TypeVar(
            "S_default_custom_selector",
            bound=SelectorBackend,
            default=SimpleSelector,
        )
        schema = TypeAdapter(
            JSONSelector[JSONValue, S_default_custom_selector]
        ).json_schema()
        assert schema["format"] == "x-json-selector"


def test_jsonselector_path_validation(subtests: Subtests) -> None:
    class SimpleSelectorSubclass(SimpleSelector):
        pass

    with subtests.test("accept strings"):
        JSONSelector.parse("a", backend=SimpleSelector)

    with subtests.test("accept compatible SelectorBackend instances"):
        JSONSelector.parse(SimpleSelector("a"), backend=SimpleSelector)

    with subtests.test("accept other JSONSelectors"):
        selector = JSONSelector.parse("a", backend=SimpleSelector)
        JSONSelector.parse(selector, backend=SimpleSelector)

    with subtests.test("reject incompatible SelectorBackends"):
        with pytest.raises(InvalidJSONSelector):
            JSONSelector.parse(DEFAULT_SELECTOR_CLS("$.a"), backend=SimpleSelector)
        with pytest.raises(InvalidJSONSelector):
            JSONSelector.parse(SimpleSelector("a"), backend=DEFAULT_SELECTOR_CLS)

    with subtests.test("accepts narrower SelectorBackends"):
        JSONSelector.parse(SimpleSelectorSubclass("a"), backend=SimpleSelector)


def test_jsonselector_covariance_narrow_to_wide(subtests: Subtests) -> None:
    with subtests.test("narrow to wide passes"):
        s_bool = JSONSelector.parse("$.x", type_param=bool)
        assert JSONSelector.parse(s_bool, type_param=int) == s_bool
        assert JSONSelector.parse(s_bool, type_param=JSONNumber) == s_bool
        assert JSONSelector.parse(s_bool, type_param=JSONValue) == s_bool


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
    If JsonPatchX trusted upstream pointer objects directly, these cases would
    stop pointing at literal ``"#..."`` object keys and would instead resolve
    to unintended targets. That is why the default backend rebuilds pointers
    from ``match.parts`` and re-exports them through JsonPatchX's RFC 6901
    pointer backend instead of leaking upstream pointer objects. See
    ``DEFAULT_SELECTOR_CLS.pointers()`` in ``jsonpatchx.backend``: that
    method intentionally rebuilds exported pointers from ``match.parts``
    instead of trusting upstream pointer objects.
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
