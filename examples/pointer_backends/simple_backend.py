from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, Self

from jsonpatch.types import PointerBackend


class DotPointer(PointerBackend):
    """
    Demonstrative pointer backend using dot-separated paths ("a.b.c").

    Notes:
    - Root pointer is the empty string.
    - No escaping is supported; empty segments are rejected.
    """

    def __init__(self, pointer: str) -> None:
        if pointer == "":
            self._parts = tuple()
            return
        if "." not in pointer:
            parts = (pointer,)
        else:
            parts = tuple(pointer.split("."))
        if any(part == "" for part in parts):
            raise ValueError("invalid dot pointer")
        self._parts = parts

    @property
    def parts(self) -> Sequence[str]:
        return self._parts

    @classmethod
    def from_parts(cls, parts: Iterable[Any]) -> Self:
        tokens = [str(p) for p in parts]
        if not tokens:
            return cls("")
        return cls(".".join(tokens))

    def resolve(self, doc: Any) -> Any:
        cur = doc
        for part in self._parts:
            if isinstance(cur, dict):
                cur = cur[part]
            elif isinstance(cur, list):
                if not part.isdigit():
                    raise KeyError("invalid list index")
                idx = int(part)
                cur = cur[idx]
            else:
                raise KeyError("non-container")
        return cur

    def __str__(self) -> str:
        return ".".join(self._parts)
