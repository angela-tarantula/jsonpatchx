from collections.abc import Iterator, MutableMapping
from types import MappingProxyType
from typing import Any, Final

from jsonpointer import JsonPointer, JsonPointerException

from jsonpatch.exceptions import (
    MemberTypeMismatch,
    MemberValueMismatch,
    MissingMember,
    UnrecognizedOperation,
)

VALID_OPS: Final = {"add", "remove", "replace", "move", "copy", "test"}


class Operation:
    """An unvalidated operation."""

    def __init__(self, definition_map: MutableMapping) -> None:
        self._definition = MappingProxyType(definition_map)

    @property
    def definition(self) -> MappingProxyType:
        """Returns the operation definition as a read-only mapping."""
        return self._definition

    def __contains__(self, item: str) -> bool:
        return item in self.definition

    def __getitem__(self, item: str) -> Any:
        return self.definition[item]

    def __iter__(self) -> Iterator[Any]:
        return iter(self.definition)

    def __len__(self) -> int:
        return len(self.definition)

    def __str__(self) -> str:
        return str(self.definition)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.definition})"

    def get(self, key: str, default: Any = None) -> Any:
        return self.definition.get(key, default)

    @property
    def name(self) -> Any:
        """Returns the best description of the operation."""
        return self.get("op", default=str(self.definition))


class PatchOperation(Operation):
    """A validated JSON Patch operation."""

    def __init__(self, definition_map: MutableMapping, pointer_cls=JsonPointer) -> None:
        super().__init__(definition_map)
        self.pointer_cls = pointer_cls
        self.validate()

    def validate(self) -> None:
        """Validate that the operation is a JSON Patch operation."""
        self._validate_op()
        self._validate_path()

    def _validate_op(self) -> None:
        """Validate the 'op' member of the operation."""
        if "op" not in self:
            raise MissingMember(self, "op")
        if not isinstance(self["op"], str):
            raise MemberTypeMismatch(self, "op")
        if self["op"] not in VALID_OPS:
            raise UnrecognizedOperation(self)

    def _validate_path(self) -> None:
        """Validate the 'path' member of the operation."""
        if "path" not in self:
            raise MissingMember(self, "path")
        match type(self["path"]):
            case str():
                try:
                    self.path_pointer = self.pointer_cls(self["path"])
                except JsonPointerException as e:
                    raise MemberValueMismatch(self, "path", str(e)) from e
            case self.pointer_cls():
                self.path_pointer = self["path"]
            case _:
                raise MemberTypeMismatch(self, "path")
