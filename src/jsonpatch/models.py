from __future__ import annotations

from collections.abc import ItemsView, Iterator, KeysView, Mapping, ValuesView
from types import MappingProxyType
from typing import Any, Callable, Literal, Required, TypeAlias, Hashable, Protocol, Self, Type, TypedDict

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)

from jsonpatch.exceptions import (
    MemberTypeMismatch,
    MemberValueMismatch,
    MissingMember,
)


class JsonPointerString(str):
    """
    A string subclass that ensures its value is a valid JSON Pointer (RFC 6901).
    """
    def __new__(cls, value: str) -> Self:
        try:
            JsonPointer(value)
        except JsonPointerException as e:
            raise ValueError(f"Invalid JSON Pointer: {value!r}") from e
        return super().__new__(cls, value)


class Operation(Mapping[str, object]):
    """
    An immutable, mapping-like representation of an operation.

    - Always has string keys.
    - Always has 'op' key and its value is a string.
    - Supports either 'from' or its synonym 'from_path', but not both.
    - Internally stores the canonical key 'from'.
    - Provides a `kwargs()` helper that is keyword-argument friendly
      (i.e. uses 'from_path' instead of 'from').
    """

    def __init__(self, fields: Mapping[str, object]) -> None:
        """
        Create an Operation from a raw mapping.

        The input is validated and normalized into an internal canonical representation.
        """
        self._data = self._prepare(fields)

    @classmethod
    def _prepare(cls, fields: Mapping[str, object]) -> Mapping[str, object]:
        """
        Validate and normalize the input fields into their canonical form.

        Rules:
        - All keys must be strings.
        - A required key 'op' must be present and must be a string.
        - 'from' and 'from_path' are mutually exclusive.
        - If 'from_path' is present, it is renamed to 'from'.
        """
        data: dict[str, object] = dict(fields)

        # Validate keys are strings
        if not all(isinstance(key, str) for key in data.keys()):
            raise TypeError("all operation keys must be strings")

        # Validate 'op' exists and is a string
        op = data.get("op")
        if op is None:
            raise TypeError("missing required 'op' member")
        if not isinstance(op, str):
            raise TypeError("member 'op' must be a string")

        # Validate mutually exclusive from/from_path
        if "from" in data and "from_path" in data:
            raise TypeError("'from' and 'from_path' are mutually exclusive keys")

        # Normalize from_path -> from
        if "from_path" in data:
            data["from"] = data.pop("from_path")

        # 
        return MappingProxyType(data)

    def kwargs(self) -> dict[str, object]:
        """
        Convert the Operation to a dictionary suitable for use as keyword arguments.

        The internal canonical key 'from' is translated back into the more
        keyword-friendly name 'from_path'. All other keys are preserved.
        """
        args: dict[str, object] = dict(self._data)
        if "from" in args:
            args["from_path"] = args.pop("from")
        return args

    @property
    def op(self) -> str:
        """Return the operation type (the value of the 'op' key)."""
        return self._data["op"] # type: ignore[return-value]

    def __contains__(self, item: object) -> bool:
        return item in self._data

    def __getitem__(self, item: str) -> object:
        return self._data[item]

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mapping):
            return dict(self._data) == dict(other)
        return NotImplemented

    def __str__(self) -> str:
        return str(self._data)

    def __repr__(self) -> str:
        return repr(self._data).replace("mappingproxy", self.__class__.__name__, count=1)

OperationSchema: TypeAlias = Callable[..., Operation]


class AddOperationDict(TypedDict):
    op: Required[Literal["add"]]
    path: Required[JsonPointerString]
    value: Required[object]


def AddOperation(
        *,
        path: JsonPointerString,
        value: object,
) -> Operation:
    return Operation(
        AddOperationDict(
            op="add",
            path=path,
            value=value
        )
    )

def MoveOperation(
        *,
        from_path: JsonPointerString,
        path: JsonPointerString,
) -> Operation:
    return Operation(
        {
            "op": "move",
            "from": from_path,
            "path": path,
        }
    )


def RemoveOperation(*, path: JsonPointerString) -> Operation:
    return Operation(
        {
            "op": "remove",
            "path": path,
        }
    )


def ReplaceOperation(
        *,
        path: JsonPointerString,
        value: object,
) -> Operation:
    return Operation(
        {
            "op": "replace",
            "path": path,
            "value": value,
        }
    )


def CopyOperation(
        *,
        from_path: JsonPointerString,
        path: JsonPointerString,
) -> Operation:
    return Operation(
        {
            "op": "copy",
            "from": from_path,
            "path": path,
        }
    )


def TestOperation(
        *,
        path: JsonPointerString,
        value: object,
) -> Operation:
    return Operation(
        {
            "op": "test",
            "path": path,
            "value": value,
        }
    )




class JsonPointerProtocol(Protocol):
    """Protocol for JSON Pointer implementations."""

    def __init__(self, pointer: str) -> None: ...




class fOperation(Mapping, Hashable):

    def __init__(self, *, op: str, **kwargs: dict[str, Hashable]) -> None:
        self.op = op
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    @property
    def definition_map(self) -> Mapping:
        result: dict[str, Hashable] = {"op": self.op}
        for key, value in self.__dict__.items():
            if key != "op":
                result[key] = value
        return result


class ffOperation(Mapping, Hashable):
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

    def __iter__(self) -> Iterator[Any]:
        return iter(self.__definition_map)

    def __hash__(self) -> int:
        return hash(frozenset(self.items()))

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, ffOperation):
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
        """Returns the name of the operation."""
        op_value = self.get("op")
        if not isinstance(op_value, str):
            return NotImplemented
        return op_value

    @property
    def _identifier(self) -> str:
        """Returns the best identifier of the operation for debugging."""
        if self.name is NotImplemented:
            return repr(dict(self))
        return self.name


class PatchOperation(ffOperation):
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

    @property
    def name(self) -> str:
        """Returns the name of the operation."""
        if super().name is NotImplemented:
            raise RuntimeError(
                f"Internal validation failed: 'op' member is missing or invalid: {self!r}"
            )
        return super().name

    def validate(self) -> None:
        """Validate that the operation is a JSON Patch operation."""
        self._validate_op()
        self._validate_path()

    def _validate_op(self) -> None:
        """Validate the 'op' member of the operation."""
        if "op" not in self:
            raise MissingMember(ffOperation(self), "op")
        elif not isinstance(self["op"], str):
            raise MemberTypeMismatch(ffOperation(self), "op")

    def _validate_path(self) -> None:
        """Validate the 'path' member of the operation."""
        if "path" not in self:
            raise MissingMember(ffOperation(self), "path")
        elif isinstance(self["path"], str):
            try:
                self.path_pointer = self.pointer_cls(self["path"])
            except JsonPointerException as e:
                raise MemberValueMismatch(ffOperation(self), "path", str(e)) from e
        elif isinstance(self["path"], self.pointer_cls):
            self.path_pointer = self["path"]
        else:
            raise MemberTypeMismatch(ffOperation(self), "path")
