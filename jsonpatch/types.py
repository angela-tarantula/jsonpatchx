from __future__ import annotations

import json
import math
from collections.abc import Hashable, Mapping, MutableMapping, MutableSequence, Sequence
from dataclasses import dataclass
from functools import lru_cache, partial
from typing import TYPE_CHECKING, Annotated, Any, Generic, TypeVar, final

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    TypeAdapter,
)
from pydantic_core import core_schema as cs
from typing_extensions import TypeForm

from jsonpatch.exceptions import (
    InvalidJSONPointer,
    InvalidOperationSchema,
    PatchApplicationError,
)

T = TypeVar("T")
T_co = TypeVar("T_co", covariant=True)
H = TypeVar("H", bound=Hashable)


class PydanticJsonValueValidator:
    """Pydantic-aware wrapper for any JSON-serializable value."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> cs.CoreSchema:
        return cs.no_info_after_validator_function(
            cls._validate,
            cs.any_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: cs.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        json_schema = handler(core_schema)
        json_schema.update({"description": "JSON Value."})
        return json_schema

    @classmethod
    def _validate(cls, v: T) -> T:
        try:
            json.dumps(v, allow_nan=False)  # TODO: switch to orjson
        except (TypeError, ValueError) as e:
            raise InvalidOperationSchema(
                f"Value is not JSON-serializable: {v!r}"
            ) from e
        return v


class StrictJSONNumberValidator:
    """Pydantic-aware wrapper for JSON numbers."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> cs.CoreSchema:
        return cs.no_info_after_validator_function(
            cls._validate,
            cs.union_schema(
                [
                    cs.float_schema(strict=True),
                    cs.int_schema(strict=True),
                ]
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        schema: cs.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        json_schema = handler(schema)
        json_schema.update({"description": "JSON Number"})
        return json_schema

    @classmethod
    def _validate(cls, v: T) -> T:
        # bool is a subclass of int, so exclude it explicitly
        if type(v) is bool or not isinstance(v, (int, float)):
            raise InvalidOperationSchema(
                f"expected JSON number (int|float, finite), not {v.__class__.__name__}: {v!r}"
            )
        if isinstance(v, float) and not math.isfinite(v):
            raise InvalidOperationSchema(f"expected finite JSON number, got {v!r}")
        return v


# Core JSON type aliases

type JSONBoolean = bool
type JSONNumber = Annotated[int | float, StrictJSONNumberValidator]
type JSONString = str
type JSONNull = None
type JSONPrimitive = JSONBoolean | JSONNumber | JSONString | JSONNull

type JSONArray[T_co] = Sequence[T_co]
type JSONObject[T_co] = Mapping[str, T_co]
type JSONContainer[T_co] = JSONArray[T_co] | JSONObject[T_co]

type MutableJSONArray[T_co] = MutableSequence[T_co]
type MutableJSONObject[T_co] = MutableMapping[str, T_co]
type MutableJSONContainer[T_co] = MutableJSONArray[T_co] | MutableJSONObject[T_co]

type JSONValue = Annotated[
    JSONPrimitive | JSONContainer[JSONValue],
    PydanticJsonValueValidator,
]


@lru_cache(maxsize=128)
def _cached_type_adapter(expected: H) -> TypeAdapter[H]:
    return TypeAdapter(expected)


@lru_cache(maxsize=128)
def _cached_json_pointer(ptr: str) -> JsonPointer:
    return JsonPointer(ptr)


def _type_adapter_for(expected: TypeForm[T_co]) -> TypeAdapter[T_co]:
    """Get a cached type adapter if possible, otherwise create a new one."""
    try:
        try:
            return _cached_type_adapter(expected)  # type: ignore[arg-type]
        except TypeError:
            return TypeAdapter(expected)
    except Exception as e:
        raise InvalidJSONPointer(f"invalid type for JSON Pointer: {expected!r}") from e


def _json_pointer_for(v: str) -> JsonPointer:
    """Get a cached JSON pointer if possible, otherwise create a new one."""
    try:
        try:
            return _cached_json_pointer(v)
        except TypeError:
            return JsonPointer(v)
    except JsonPointerException as e:
        raise InvalidJSONPointer(f"invalid JSON Pointer: {v!r}") from e


@final
class _TypedJSONPointer(str, Generic[T_co]):
    """
    Runtime value produced by Pydantic for a field annotated as JSONPointer[T].

    - Subclasses str (so it behaves like the pointer string)
    - Stores parsed JsonPointer for structural ops
    - Stores TypeAdapter[T] for apply-time validation
    """

    __slots__ = ("_ptr", "_adapter", "_type_repr")

    _ptr: JsonPointer
    _adapter: TypeAdapter[T_co]
    _type_repr: str

    def __new__(cls, v: str) -> "_TypedJSONPointer[T_co]":
        # Prevent user construction; go through Pydantic validation.
        raise InvalidJSONPointer(
            "JSONPointer values are created by Pydantic validation only."
        )

    @classmethod
    def _from_str(
        cls, v: str, *, expected: TypeForm[T_co]
    ) -> "_TypedJSONPointer[T_co]":
        """Intended route for construction of _TypedJSONPointer[T_co]."""
        if not isinstance(v, str):
            # defensive, Pydantic should have already caught this
            raise InvalidJSONPointer(f"invalid JSON Pointer: {v!r} is not a string")
        obj = str.__new__(cls, v)
        obj._ptr = _json_pointer_for(v)
        obj._adapter = _type_adapter_for(expected)
        obj._type_repr = repr(expected)
        return obj

    def validate_pointed_value(self, value: Any) -> T_co:
        """Apply-time validation: ensure the runtime value is assignable to T_co"""
        try:
            return self._adapter.validate_python(value, strict=True)
        except Exception as e:
            raise PatchApplicationError(
                f"value at {str(self)!r} is not assignable to {self._type_repr}"
            ) from e


if TYPE_CHECKING:
    # Public ergonomics: JSONPointer[T_co] is just str to type checkers
    type JSONPointer[T_co] = str
else:

    @dataclass(frozen=True, slots=True)
    class JSONPointer(Generic[T_co]):
        """
        JSON Pointer (RFC 6901) string, with Pydantic-aware validation.

        Type-checkers treat JSONPointer[T_co] as str, but at runtime Pydantic returns _TypedJSONPointer[T_co].
        """

        type: TypeForm[T_co]

        @classmethod
        def __class_getitem__(cls, expected: TypeForm[T_co]) -> Any:
            return Annotated[str, cls(type=expected)]

        def __get_pydantic_core_schema__(
            self,
            source_type: Any,
            handler: GetCoreSchemaHandler,
        ) -> cs.CoreSchema:
            return cs.no_info_after_validator_function(
                function=partial(_TypedJSONPointer._from_str, expected=self.type),
                schema=cs.str_schema(
                    strict=True
                ),  # In OpenAPI/JSON schema, a pointer is a string
            )

        def __get_pydantic_json_schema__(
            self,
            schema: cs.CoreSchema,
            handler: GetJsonSchemaHandler,
        ) -> dict[str, object]:
            json_schema = handler(schema)
            json_schema.update({"description": "JSON Pointer (RFC 6901) string."})
            return json_schema


x: JSONPointer[JSONValue] = "/foo/bar"
