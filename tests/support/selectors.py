from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import assert_never, cast, override

from jsonpatchx.backend import (
    _DEFAULT_POINTER_CLS,
    PointerBackend,
    SelectorBackend,
    SelectorMatch,
)
from jsonpatchx.types import JSONValue


@dataclass(frozen=True, slots=True)
class SimpleSelectorMatch(SelectorMatch):
    obj: JSONValue
    parts: tuple[int | str, ...]

    @override
    def pointer(self) -> PointerBackend:
        return _DEFAULT_POINTER_CLS.from_parts(self.parts)


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
            "bad_match",
        }
        if selector not in allowed:
            raise ValueError(f"invalid simple selector: {selector!r}")
        self._selector = selector

    @override
    def pointers(self, doc: JSONValue) -> Iterable[PointerBackend]:
        return [match.pointer() for match in self.finditer(doc)]

    @override
    def finditer(self, doc: JSONValue) -> Iterable[SelectorMatch]:
        match self._selector:
            case "root":
                return [SimpleSelectorMatch(doc, ())]
            case "a":
                root = doc
                if not isinstance(root, dict):
                    raise TypeError("root is not an object")
                return [SimpleSelectorMatch(root["a"], ("a",))]
            case "a.b":
                root = doc
                if not isinstance(root, dict) or not isinstance(root["a"], dict):
                    raise TypeError("a is not an object")
                return [SimpleSelectorMatch(root["a"]["b"], ("a", "b"))]
            case "all_items":
                root = doc
                if not isinstance(root, dict) or not isinstance(root["items"], list):
                    raise TypeError("items is not an array")
                return [
                    SimpleSelectorMatch(item, ("items", index))
                    for index, item in enumerate(root["items"])
                ]
            case "double_a":
                root = doc
                if not isinstance(root, dict):
                    raise TypeError("root is not an object")
                return [
                    SimpleSelectorMatch(root["a"], ("a",)),
                    SimpleSelectorMatch(root["a"], ("a",)),
                ]
            case "items_0_1":
                root = doc
                if not isinstance(root, dict) or not isinstance(root["items"], list):
                    raise TypeError("items is not an array")
                items = root["items"]
                return [
                    SimpleSelectorMatch(items[0], ("items", 0)),
                    SimpleSelectorMatch(items[1], ("items", 1)),
                ]
            case "record_values":
                root = doc
                if not isinstance(root, dict) or not isinstance(root["record"], dict):
                    raise TypeError("record is not an object")
                record = root["record"]
                return [
                    SimpleSelectorMatch(value, ("record", key))
                    for key, value in record.items()
                ]
            case "missing":
                return []
            case "root_and_a":
                root = doc
                if not isinstance(root, dict):
                    raise TypeError("root is not an object")
                return [
                    SimpleSelectorMatch(root, ()),
                    SimpleSelectorMatch(root["a"], ("a",)),
                ]
            case "bad_match":
                return [cast(SelectorMatch, object())]
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


class SelectorMissingFinditer(SelectorBackend):
    """SimpleSelector but without finditer()."""

    __init__ = SimpleSelector.__init__

    pointers = SimpleSelector.pointers

    __str__ = SimpleSelector.__str__


class SelectorMissingPointers(SelectorBackend):
    """SimpleSelector but without pointers()."""

    __init__ = SimpleSelector.__init__

    finditer = SimpleSelector.finditer

    __str__ = SimpleSelector.__str__
