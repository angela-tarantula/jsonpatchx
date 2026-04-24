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
    Tiny deterministic selector backend for unit tests.

    This is a test double for ``SelectorBackend``, not a real JSONPath engine.
    It exposes a small fixed set of selector strings so selector unit tests can
    exercise JsonPatchX's own wrapper semantics without depending on full
    JSONPath parsing or evaluation behavior.
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
