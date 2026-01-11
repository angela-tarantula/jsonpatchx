from collections.abc import Iterable
from typing import Any, Literal, override

from jsonpatchx.registry import GenericOperationRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONPointer, JSONValue, PointerBackend


class DotPointer(PointerBackend):
    def __init__(self, pointer: str) -> None:
        self._parts = [] if pointer == "" else pointer.split(".")

    @property
    @override
    def parts(self) -> list[str]:
        return self._parts

    @classmethod
    @override
    def from_parts(cls, parts: Iterable[Any]) -> "DotPointer":
        return cls(".".join(parts))

    @override
    def resolve(self, doc: JSONValue) -> Any:
        cur: Any = doc
        for token in self._parts:
            cur = cur[token]
        return cur

    @override
    def __str__(self) -> str:
        return ".".join(self._parts)


class DotRemoveOp(OperationSchema):
    op: Literal["dot-remove"] = "dot-remove"
    path: JSONPointer[JSONValue, DotPointer]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return self.path.remove(doc)


def test_custom_backend_with_registry() -> None:
    registry = GenericOperationRegistry[DotRemoveOp, DotPointer]
    patch = JsonPatch([{"op": "dot-remove", "path": "a.b"}], registry=registry)
    result = patch.apply({"a": {"b": 1}})
    assert result == {"a": {}}
