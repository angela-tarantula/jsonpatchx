from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Self

from jsonpatchx.backend import PointerBackend
from jsonpatchx.types import JSONValue


class IncompletePointerBackend:
    """A PointerBackend missing required methods."""

    def __init__(self, pointer: str) -> None:
        self._parts = [] if pointer == "" else pointer.split(".")

    @property
    def parts(self) -> list[str]:
        return self._parts

    @classmethod
    def from_parts(cls, parts: Iterable[Any]) -> Self:
        return cls(".".join(str(p) for p in parts))

    def __str__(self) -> str:
        return ".".join(self._parts)


class AnotherIncompletePointerBackend(IncompletePointerBackend, PointerBackend):
    """IncompletePointerBackend but it technically inherits from PointerBackend."""

    pass


class DotPointer(IncompletePointerBackend):
    def __init__(self, pointer: str) -> None:
        if ".." in pointer:
            raise ValueError("invalid dot pointer")
        super().__init__(pointer)

    def resolve(self, data: JSONValue) -> Any:
        cur: Any = data
        for token in self._parts:
            cur = cur[token]
        return cur


class DotPointerSubclass(DotPointer):
    """Narrower DotPointer variant reused across pointer covariance tests."""

    pass


class BadDotPointer(DotPointer):
    """Looks like a valid DotPointer until runtime."""

    def __new__(cls, pointer: str) -> str:
        return "nope"


class PointerMissingParts(PointerBackend):
    __init__ = DotPointer.__init__

    from_parts = DotPointer.from_parts

    __str__ = DotPointer.__str__

    __hash__ = DotPointer.__hash__
