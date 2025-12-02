from collections.abc import ItemsView, KeysView, Mapping, ValuesView
from types import MappingProxyType
from typing import Any, Hashable, Protocol, Type

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)

from jsonpatch.exceptions import (
    MemberTypeMismatch,
    MemberValueMismatch,
    MissingMember,
)


class JsonPointerProtocol(Protocol):
    """Protocol for JSON Pointer implementations."""

    def __init__(self, pointer: str) -> None: ...


class Operation(Mapping, Hashable):
    """An unvalidated operation."""

    __slots__ = ("__definition_map",)

    def __init__(self, definition_map: Mapping) -> None:
        self.__definition_map = MappingProxyType(definition_map)

    def __contains__(self, item: Any) -> bool:
        return item in self.__definition_map

    def __getitem__(self, item: Any) -> Any:
        return self.__definition_map[item]

    def __len__(self) -> int:
        return len(self.__definition_map)

    def __iter__(self):
        return iter(self.__definition_map)

    def __hash__(self):
        return hash(frozenset(self.items()))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Operation):
            return NotImplemented
        return self.__definition_map == other.__definition_map

    def __str__(self) -> str:
        return str(self.__definition_map)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.__definition_map})"

    def get(self, key: str, default: Any = None) -> Any:
        return self.__definition_map.get(key, default)

    def keys(self) -> KeysView[Any]:
        return self.__definition_map.keys()

    def values(self) -> ValuesView[Any]:
        return self.__definition_map.values()

    def items(self) -> ItemsView[Any, Any]:
        return self.__definition_map.items()

    @property
    def name(self) -> str:
        """Returns the best description of the operation."""
        op_value = self.get("op")
        if isinstance(op_value, str):
            return op_value
        return str(self.__definition_map)


class PatchOperation(Operation):
    """A validated JSON Patch operation."""

    __slots__ = ("pointer_cls", "path_pointer")

    def __init__(
        self,
        definition_map: Mapping,
        pointer_cls: Type[JsonPointerProtocol] = JsonPointer,
    ) -> None:
        super().__init__(definition_map)
        self.pointer_cls = pointer_cls
        self.path_pointer: JsonPointerProtocol
        self.validate()

    def validate(self) -> None:
        """Validate that the operation is a JSON Patch operation."""
        self._validate_op()
        self._validate_path()

    def _validate_op(self) -> None:
        """Validate the 'op' member of the operation."""
        if "op" not in self:
            raise MissingMember(Operation(self), "op")
        elif not isinstance(self["op"], str):
            raise MemberTypeMismatch(Operation(self), "op")

    def _validate_path(self) -> None:
        """Validate the 'path' member of the operation."""
        if "path" not in self:
            raise MissingMember(Operation(self), "path")
        elif isinstance(self["path"], str):
            try:
                self.path_pointer = self.pointer_cls(self["path"])
            except JsonPointerException as e:
                raise MemberValueMismatch(Operation(self), "path", str(e)) from e
        elif isinstance(self["path"], self.pointer_cls):
            self.path_pointer = self["path"]
        else:
            raise MemberTypeMismatch(Operation(self), "path")
