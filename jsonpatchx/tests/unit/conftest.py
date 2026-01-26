from collections.abc import Iterable
from typing import Any, Self

from jsonpatchx.types import JSONValue, PointerBackend


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

    def __hash__(self) -> int:
        return hash(tuple(self._parts))


class DotPointer(IncompletePointerBackend):
    def resolve(self, doc: JSONValue) -> Any:
        cur: Any = doc
        for token in self._parts:
            cur = cur[token]
        return cur


class BadPointer(DotPointer):
    """A PointerBackend that refuses the empty string."""

    def __init__(self, pointer: str) -> None:
        if not pointer:
            raise ValueError("BadPointer does not accept the empty string")


class AnotherIncompletePointerBackend(PointerBackend):
    """A PointerBackend that does not implement all abstract methods."""

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

    def __hash__(self) -> int:
        return hash(tuple(self._parts))
