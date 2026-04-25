from __future__ import annotations

from collections.abc import Iterable
from typing import assert_never, cast, override

from jsonpatchx.backend import (
    _DEFAULT_POINTER_CLS,
    PointerBackend,
    SelectorBackend,
)
from jsonpatchx.types import JSONValue


class SimpleSelector(SelectorBackend):
    """
    Crude mocked selector implementation for unit tests.

    This is not a real JSONPath engine. It is a deliberately tiny fake
    ``SelectorBackend`` with a hardcoded set of selector strings and equally
    hardcoded traversal behavior. Its job is only to let selector unit tests
    exercise backend-agnostic JsonPatchX wrapper semantics without depending on
    real JSONPath parsing, evaluation, or edge cases.
    """

    def __init__(self, selector: str) -> None:
        allowed = {
            "root",
            "a",
            "a.b",
            "all_items",
            "double_a",
            "items_0_1",
            "record_values",
            "missing",
            "root_and_a",
            "bad_pointer",
        }
        if selector not in allowed:
            raise ValueError(f"invalid simple selector: {selector!r}")
        self._selector = selector

    @override
    def pointers(self, doc: JSONValue) -> Iterable[PointerBackend]:
        def ptr(parts: tuple[int | str, ...]) -> PointerBackend:
            return _DEFAULT_POINTER_CLS.from_parts(parts)

        match self._selector:
            case "root":
                return [ptr(())]
            case "a":
                root = doc
                if not isinstance(root, dict):
                    raise TypeError("root is not an object")
                return [ptr(("a",))]
            case "a.b":
                root = doc
                if not isinstance(root, dict) or not isinstance(root["a"], dict):
                    raise TypeError("a is not an object")
                return [ptr(("a", "b"))]
            case "all_items":
                root = doc
                if not isinstance(root, dict) or not isinstance(root["items"], list):
                    raise TypeError("items is not an array")
                return [ptr(("items", index)) for index, _ in enumerate(root["items"])]
            case "double_a":
                root = doc
                if not isinstance(root, dict):
                    raise TypeError("root is not an object")
                return [
                    ptr(("a",)),
                    ptr(("a",)),
                ]
            case "items_0_1":
                root = doc
                if not isinstance(root, dict) or not isinstance(root["items"], list):
                    raise TypeError("items is not an array")
                return [
                    ptr(("items", 0)),
                    ptr(("items", 1)),
                ]
            case "record_values":
                root = doc
                if not isinstance(root, dict) or not isinstance(root["record"], dict):
                    raise TypeError("record is not an object")
                record = root["record"]
                return [ptr(("record", key)) for key in record]
            case "missing":
                return []
            case "root_and_a":
                root = doc
                if not isinstance(root, dict):
                    raise TypeError("root is not an object")
                return [
                    ptr(()),
                    ptr(("a",)),
                ]
            case "bad_pointer":
                return [cast(PointerBackend, object())]
            case _ as unreachable:
                assert_never(unreachable)

    @override
    def __str__(self) -> str:
        return self._selector

    @override
    def __repr__(self) -> str:
        return f"SimpleSelector({self._selector!r})"


class IncompleteSelectorBackend:
    """A SelectorBackend missing required methods."""

    __init__ = SimpleSelector.__init__

    __str__ = SimpleSelector.__str__


class AnotherIncompleteSelectorBackend(IncompleteSelectorBackend, SelectorBackend):
    """IncompleteSelectorBackend but it technically inherits from SelectorBackend."""

    pass


class BadSimpleSelector(SimpleSelector):
    """Looks like a valid SimpleSelector until runtime."""

    def __new__(cls, selector: str) -> str:
        return "nope"


class SelectorMissingPointers(SelectorBackend):
    """SimpleSelector but without pointers()."""

    __init__ = SimpleSelector.__init__

    __str__ = SimpleSelector.__str__
