from types import MappingProxyType
from typing import Any, MutableMapping

from jsonpatch.exceptions import MissingMember


class Operation:
    """An unvalidated operation."""

    def __init__(self, definition_map: MutableMapping, *args, **kwargs):
        self._definition = MappingProxyType(definition_map)
        self.args = args
        self.kwargs = kwargs

    @property
    def definition(self) -> MappingProxyType:
        """Returns the operation definition as a read-only mapping."""
        return self._definition

    def __contains__(self, item: str) -> bool:
        return item in self.definition

    def __getitem__(self, item: str) -> Any:
        return self.definition[item]

    def __iter__(self):
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

    def __init__(self, definition_map: MutableMapping, *args, **kwargs):
        super().__init__(definition_map, *args, **kwargs)
        self.validate()

    def validate(self) -> None:
        if "op" not in self.definition:
            raise MissingMember(self, "op")
