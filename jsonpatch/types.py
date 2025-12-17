from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence
from functools import lru_cache
from typing import Annotated, Any, ClassVar, Generic, Self, TypeVar

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler, TypeAdapter
from pydantic_core import core_schema

from jsonpatch.exceptions import InvalidOperationSchema


class PydanticJsonValueValidator:
    """Pydantic-aware wrapper for any JSON-serializable value."""

    VALUE_GENERIC = TypeVar("VALUE_GENERIC")

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        # Use a permissive schema and let the validator enforce JSON-serializability
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.any_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        json_schema = handler(core_schema)
        json_schema.update({"description": "Any JSON-serializable value."})
        return json_schema

    @classmethod
    def _validate(cls, v: VALUE_GENERIC) -> VALUE_GENERIC:
        try:
            json.dumps(v, allow_nan=False)  # TODO: switch to orjson
        except (TypeError, ValueError) as e:
            raise InvalidOperationSchema(
                f"Value is not JSON-serializable: {v!r}"
            ) from e
        return v


class StrictJSONNumberValidator:
    """Pydantic-aware wrapper for JSON numbers."""

    NUMBER_GENERIC = TypeVar("NUMBER_GENERIC", int, float)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.union_schema(
                [
                    core_schema.int_schema(strict=True),
                    core_schema.float_schema(strict=True),
                ]
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        json_schema = handler(schema)
        json_schema.update({"description": "number (int|float)"})
        return json_schema

    @classmethod
    def _validate(cls, v: NUMBER_GENERIC) -> NUMBER_GENERIC:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise InvalidOperationSchema(
                f"Expected JSON number (int|float), not {v.__class__.__name__}: {v!r}"
            )
        return v


# Core JSON type aliases

type JSONBoolean = bool
type JSONNumber = Annotated[int | float, StrictJSONNumberValidator]
type JSONString = str
type JSONNull = None
type JSONPrimitive = JSONBoolean | JSONNumber | JSONString | JSONNull

T = TypeVar("T")

type JSONArray[T] = Sequence[T]
type JSONObject[T] = Mapping[str, T]
type JSONContainer[T] = JSONArray[T] | JSONObject[T]

type MutableJSONArray[T] = MutableSequence[T]
type MutableJSONObject[T] = MutableMapping[str, T]
type MutableJSONContainer[T] = MutableJSONArray[T] | MutableJSONObject[T]

type JSONValue = Annotated[
    JSONPrimitive | JSONContainer[JSONValue],
    PydanticJsonValueValidator,
]


class PydanticJsonPointerValidator:
    """Pydantic-aware wrapper for JSON Pointers."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate, core_schema.str_schema()
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        """Expose JSON Pointer as a string with a 'json-pointer' format hint."""
        json_schema = handler(core_schema)
        json_schema.update({"format": "json-pointer"})
        return json_schema

    @classmethod
    def _validate(cls, v: str) -> str:
        try:
            JsonPointer(v)
        except JsonPointerException as e:
            raise InvalidOperationSchema(f"Invalid JSON Pointer: {v!r}") from e
        return v


@lru_cache(maxsize=256)
def _adapter_for(tp: object) -> TypeAdapter[object]:
    """Cache `TypeAdapter` instances for expected value types, which can be non-trivial nested generics."""
    return TypeAdapter(tp)


class JSONPointer(str, Generic[T]):
    """
    A subclass of `str` with JSON Pointer syntax validated at parse-time.

    Optionally value-typed: `JSONPointer[T]` carries `T` so callers can
    validate the value at that pointer at apply-time.
    """

    __expected_type__: ClassVar[object] = object  # not required to be set!
    _ptr: JsonPointer
    _adapter: TypeAdapter[Any]

    def __new__(cls, v: str) -> Self:
        try:
            ptr = JsonPointer(v)
        except JsonPointerException as e:
            raise InvalidOperationSchema(f"Invalid JSON Pointer: {v!r}") from e

        obj = str.__new__(cls, v)
        obj._ptr = ptr
        obj._adapter = _adapter_for(getattr(cls, "__expected_type__", Any))
        return obj

    @classmethod
    def __class_getitem__(cls, generic: T) -> type["JSONPointer[T]"]:
        # Return a specialized *subclass* that carries the expected type.
        name = f"{cls.__name__}[{getattr(generic, '__name__', repr(generic))}]"
        return type(name, (cls,), {"__expected_type__": generic})

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[Any], handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls,  # calls __new__
            core_schema.str_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, object]:
        js = handler(schema)
        js.update(
            {"type": "string", "format": "json-pointer"}
        )  # check if need type: string here
        return js

    def to_last(self, doc: JSONValue) -> tuple[JSONContainer[JSONValue], JSONValue]:
        return self._ptr.to_last(doc)  # type: ignore[no-any-return]  # this is because JsonPointer is untyped

    def contains(self, other: "JSONPointer[Any]") -> bool:
        return self._ptr.contains(other._ptr)  # type: ignore[no-any-return]  # this is because JsonPointer is untyped

    def validate_pointed_value(self, value: Any) -> T:
        return self._adapter.validate_python(value, strict=True)  # type: ignore[no-any-return]  # we know the validated object is T, not Any


# type JSONPointer = Annotated[str, PydanticJsonPointerValidator]
