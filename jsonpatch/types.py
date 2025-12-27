from __future__ import annotations

import re
from collections.abc import Sequence
from functools import cached_property, lru_cache
from typing import (
    Annotated,
    Any,
    Literal,
    Protocol,
    Self,
    TypeGuard,
    cast,
    final,
    get_args,
    override,
    runtime_checkable,
)

from annotated_types import Ge
from jsonpointer import JsonPointer  # type: ignore[import-untyped]
from pydantic import (
    Field,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    TypeAdapter,
)
from pydantic_core import core_schema as cs
from typing_extensions import TypeForm

from jsonpatch.exceptions import (
    InvalidJSONPointer,
    PatchApplicationError,
)

# Core, Pydantic-aware JSON type aliases

type JSONBoolean = Annotated[bool, Field(strict=True)]
type JSONNumber = (
    Annotated[int, Field(strict=True)]
    | Annotated[float, Field(strict=True, allow_inf_nan=False)]
)
type JSONString = Annotated[str, Field(strict=True)]
type JSONNull = None
type JSONPrimitive = JSONBoolean | JSONNumber | JSONString | JSONNull

type JSONArray[T_co] = Annotated[list[T_co], Field(strict=True)]
type JSONObject[T_co] = Annotated[dict[str, T_co], Field(strict=True)]
type JSONContainer[T_co] = JSONArray[T_co] | JSONObject[T_co]

type JSONValue = Annotated[
    JSONPrimitive | JSONContainer[JSONValue],
    Field(description="JSON value (RFC-style primitives, list, dict)"),
]


def _is_container(value: JSONValue) -> TypeGuard[JSONContainer[JSONValue]]:
    return isinstance(value, (dict, list))


# Internal type hints

type _JSONArrayKey = Annotated[int, Ge(0)] | Literal["-"]
type _JSONObjectKey = str
type _JSONKey = _JSONArrayKey | _JSONObjectKey


# Agnostic JSON Pointer implementation.


@runtime_checkable
class PointerBackend(Protocol):
    """A simple JSON Pointer protocol, serving as the backend for the mutative JSONPointer[T] wrapper."""

    def __init__(self, pointer: str, **kwargs: Any) -> None:
        """RFC6901 JSON Pointer initializer."""
        ...

    @property
    def parts(self, **kwargs: Any) -> Sequence[str]:
        """A sequence of RFC6901-unescaped tokens. The root pointer has an empty sequence of parts."""
        ...

    @classmethod
    def from_parts(cls, parts: Sequence[str], **kwargs: Any) -> Self:
        """Construct an RFC6901 JSON Pointer from a sequence of unescaped tokens."""
        ...

    def resolve(self, doc: Any, **kwrargs: Any) -> JSONValue:
        """Resolve pointer against doc, following RFC6901 semantics."""

    @override
    def __str__(self) -> str:
        """
        Get the string representation of the pointer (i.e. RFC6901-escaped parts).

        From a mathematical point of view, it must preserve the following invariant:
        - PointerBackend(x) == PointerBackend(str(PointerBackend(x))).
        """
        ...


# Internal logic to use any JSON Pointer implementation to mutate JSON.
# Advanced users will be able to plug-and-play with their own JSON Pointer implementation
# if they want, but this library will provide basic, naive logic.
# An example of a specialized JSON Pointer implementation that I don't want to reinvent
# would be: https://github.com/jg-rp/python-jsonpath/blob/main/jsonpath/pointer.py

_ArrayIndexPattern: re.Pattern[str] = re.compile(r"^(0|[1-9][0-9]*)$")


def _parse_JSONArray_key(array: JSONArray[JSONValue], key: str) -> _JSONArrayKey:
    assert isinstance(array, list), "internal error: _parse_JSONArray_key"
    if key == "-":
        return "-"
    if not _ArrayIndexPattern.fullmatch(key):
        raise PatchApplicationError(f"invalid array index: {key!r}")
    idx = int(key)
    if idx >= len(array):
        raise PatchApplicationError(f"index out of range: {key!r}")
    return idx


def _parse_JSONContainer_key(
    container: JSONContainer[JSONValue], token: str
) -> _JSONKey:
    assert isinstance(container, (dict, list)), (
        "internal error: _parse_JSONContainer_key"
    )
    # NOTE: when type-checker type narrowing improves, refactor this method to return
    # tuple[JSONArray[JSONValue], _JSONArrayKey] | tuple[JSONObject[JSONValue], _JSONObjectKey].
    # Currently, type-checkers miss that specificity and coerce to tuple[JSONContainer[JSONValue], _JSONKey]
    if isinstance(container, dict):
        return token
    return _parse_JSONArray_key(container, token)


@lru_cache(maxsize=128)
def _cached_type_adapter[T](expected: TypeForm[T]) -> TypeAdapter[T]:
    # https://docs.pydantic.dev/latest/concepts/performance/#typeadapter-instantiated-once
    return TypeAdapter(expected)


@lru_cache(maxsize=128)
def _cached_json_pointer(
    ptr: str, *, pointer_cls: type[PointerBackend]
) -> PointerBackend:
    # a cache here too doesn't hurt, to be implementation-agnostic
    pointer = pointer_cls(ptr)
    if not isinstance(pointer, PointerBackend):
        raise InvalidJSONPointer(
            f"pointer class {pointer_cls.__name__} does not conform to the standard"
        )
    return pointer


def _type_adapter_for[T](expected: TypeForm[T]) -> TypeAdapter[T]:
    """Get a cached type adapter if possible, otherwise create a new one."""
    try:
        try:
            return _cached_type_adapter(expected)  # type: ignore[arg-type] # catching TypeError
        except TypeError:
            return TypeAdapter(expected)
    except Exception as e:
        raise InvalidJSONPointer(
            f"invalid type parameter for JSON Pointer: {expected!r}"
        ) from e


def _json_pointer_for(v: str, *, cls: type[PointerBackend]) -> PointerBackend:
    """Get a cached JSON pointer."""
    try:
        return _cached_json_pointer(v, cls=cls)
    except Exception as e:
        raise InvalidJSONPointer(f"invalid JSON Pointer: {v!r}") from e


_Nothing = object()


@final
class JSONPointer[T: JSONValue](str):
    """
    RFC6901 JSON Pointer. Runtime value produced by Pydantic for a field annotated as JSONPointer[IN, OUT].

    - Subclasses str so user code can treat it like the pointer string.
    - Stores parsed PointerBackend for structural ops
    - Stores TypeAdapter[T] for apply-time validation
    """

    __slots__ = ("_ptr", "_adapter")

    _ptr: PointerBackend
    _adapter: TypeAdapter[T]

    @property
    def ptr(self) -> Any:
        """The JSON Pointer class for this JSONPointer[T], exposed for advanced users."""
        # TODO: Change 'Any' to the actual JSON Pointer class they pass in
        return self._ptr

    @cached_property
    def _parent_ptr(self) -> PointerBackend:
        return self._ptr.__class__.from_parts(self.parts[:-1])

    @property
    def type(self) -> TypeForm[T]:
        # Shamelessly relies on a private property, TypeAdapter._type, to get the JSONPointer type.
        # In my opinion, TypeAdapter._type should be a public property, and I'll die on this hill.
        # If I had JSONPointer._adapter and JSONPointer._type, there'd be two sources of truth.
        # JSONPointer._type would be a derived property, and I'm too purist to implement it.
        return cast(TypeForm[T], self._adapter._type)

    @property
    def parts(self) -> Sequence[str]:
        """A sequence of RFC6901-unescaped pointer components."""
        return self._ptr.parts

    def __new__(cls, *_: object, **__: object) -> Self:
        raise TypeError("JSONPointer values are created by Pydantic validation only.")

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> cs.CoreSchema:
        # Pydantic passes the parameterized type (JSONPointer[JSONString, JSONBoolean]) as source_type
        args = get_args(source_type)
        if not args:
            raise InvalidJSONPointer(
                "JSONPointer must be parameterized, e.g. JSONPointer[JSONNumber, JSONNumber]"
            )
        elif 1 < len(args):
            raise InvalidJSONPointer(
                f"JSONPointer may only have 1 parameter, got {len(args)}: {args}"
            )
        else:
            expected_type: TypeForm[T] = cast(TypeForm[T], args[0])

        def initializer(v: str) -> Self:
            # TODO: if v is JSONPointer[T] already, return v (requires enabling the __new__ method for user instantiation)
            if type(v) is not str:  # defensive
                raise InvalidJSONPointer(f"invalid JSON Pointer: {v!r} is not a string")
            obj = str.__new__(cls, v)
            obj._ptr = _json_pointer_for(v, cls=JsonPointer)
            obj._adapter = _type_adapter_for(expected_type)
            return obj

        return cs.no_info_after_validator_function(
            function=initializer,
            schema=cs.str_schema(strict=True),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, object]:
        json_schema = handler(schema)
        json_schema.update(
            {
                "type": "string",
                "format": "json-pointer",
                "description": "JSON Pointer (RFC 6901) string",
            }
        )
        return json_schema

    def validate_target(self, target: object) -> T:
        """
        Validate a target against this pointer's type.

        Raises PatchApplicationError on failure.
        """
        try:
            return self._adapter.validate_python(target, strict=True)
        except Exception as e:
            raise PatchApplicationError(
                f"invalid target type {type(target).__name__} for pointer {str(self)!r}"
            ) from e

    def is_root(self) -> bool:
        """Check whether this JSONPointer's target is the root."""
        return self == ""

    def is_parent_of(self, other: JSONPointer[Any]) -> bool:
        """
        Check whether this JSONPointer's path is a parent of the `other` JSONPointer's path.

        Root is treated as a parent of all paths.
        """
        # Strict parentage only
        if self == other:
            return False

        return other.parts[: len(self.parts)] == self.parts

    def get(self, doc: JSONValue) -> T:
        """Resolve the JSONPointer against the `doc` and return the target."""
        target = self._ptr.resolve(doc)
        return self.validate_target(target)

    def is_gettable(self, doc: JSONValue) -> bool:
        try:
            self.get(doc)
        except Exception:
            return False
        else:
            return True

    def set(self, doc: JSONValue, value: T) -> JSONValue:
        target = self.validate_target(target=value)
        if self.is_root():
            return target
        container = self._parent_ptr.resolve(doc)
        if not _is_container(container):
            raise PatchApplicationError(
                f"cannot set value at {str(self)!r} because {self._parent_ptr} resolves to a JSON primitive"
            )
        key = _parse_JSONContainer_key(container, self.parts[-1])
        if key == "-" and not isinstance(container, dict):
            container.append(key)
        else:
            container[key] = value  # type: ignore[index]
        return doc

    def is_settable(self, doc: JSONValue, value: object = _Nothing) -> bool:
        try:
            if value is not _Nothing:
                self.validate_target(value)
            if self.is_root():
                return True
            container = self._parent_ptr.resolve(doc)
            if not _is_container(container):
                return False
            _parse_JSONContainer_key(container, self.parts[-1])
        except Exception:
            return False
        else:
            return True

    def delete(self, doc: JSONValue) -> JSONValue:
        if self.is_root():
            raise PatchApplicationError("cannot delete the root")
        if not self.is_gettable(doc):
            raise PatchApplicationError("cannot delete a missing target")
        container = cast(JSONContainer[JSONValue], self._parent_ptr.resolve(doc))
        key = _parse_JSONContainer_key(container, self.parts[-1])
        if key == "-" and not isinstance(container, dict):
            raise PatchApplicationError(
                f"cannot delete value at {str(self)!r} with key '-'"
            )
        del container[key]  # type: ignore[arg-type]
        return doc

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}[{self.type}]({str(self)!r})"
