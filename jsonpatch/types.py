from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence
from functools import cache
from typing import (
    Annotated,
    Any,
    ClassVar,
    Generic,
    Literal,
    Self,
    TypeVar,
    final,
)

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler, TypeAdapter
from pydantic_core import core_schema
from typing_extensions import TypeForm

from jsonpatch.exceptions import (
    InvalidJSONPointer,
    InvalidOperationSchema,
    PatchApplicationError,
)


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

_T_co = TypeVar("_T_co", covariant=True)

type JSONArray[_T_co] = Sequence[_T_co]
type JSONObject[_T_co] = Mapping[str, _T_co]
type JSONContainer[_T_co] = JSONArray[_T_co] | JSONObject[_T_co]

type MutableJSONArray[_T_co] = MutableSequence[_T_co]
type MutableJSONObject[_T_co] = MutableMapping[str, _T_co]
type MutableJSONContainer[_T_co] = MutableJSONArray[_T_co] | MutableJSONObject[_T_co]

type JSONValue = Annotated[
    JSONPrimitive | JSONContainer[JSONValue],
    PydanticJsonValueValidator,
]


@final
class JSONPointer(str, Generic[_T_co]):
    """
    A subclass of `str` with JSON Pointer syntax validated at parse-time. Specifying a type parameter is required.

    JSONPointer[A] and JSONPointer[B] are different classes (if A != B), each with its own expected type (A and B,
    respectively) for the pointed value.
    """

    __slots__ = ("_ptr",)
    _ptr: JsonPointer

    # Generic ClassVars are OK here because JSONPointer[A] and JSONPointer[B] are different classes (ref: https://github.com/python/typing/discussions/1424#discussioncomment-7989934)
    __expected_type__: ClassVar[TypeForm[_T_co]]
    __adapter__: ClassVar[TypeAdapter[_T_co]]

    @classmethod
    def _init_adapter(cls) -> TypeAdapter[_T_co]:
        """Cache the TypeAdapter for the expected type."""
        try:
            cls.__expected_type__
        except AttributeError:
            raise InvalidJSONPointer(
                "missing expected type: JSONPointer must be specialized with a type (e.g., JSONPointer[JSONValue] or JSONPointer[JSONArray[JSONNumber]])"
            )

        try:
            return cls.__adapter__
        except AttributeError:
            try:
                cls.__adapter__ = TypeAdapter(cls.__expected_type__)
                return cls.__adapter__
            except Exception as e:
                raise InvalidJSONPointer(
                    f"invalid expected type {cls.__expected_type__!r}"
                ) from e

    def __new__(cls, v: str) -> Self:
        cls._init_adapter()
        try:
            ptr = JsonPointer(v)
        except JsonPointerException as e:
            raise InvalidJSONPointer(f"invalid syntax: {v!r}") from e

        obj = str.__new__(cls, v)
        obj._ptr = ptr
        return obj

    @classmethod
    @cache
    def __class_getitem__(
        cls, generic: TypeForm[_T_co]
    ) -> type["JSONPointer[_T_co]"]:  # lie to mypy that it's not a subclass
        """Return a specialized *subclass* that carries the expected type."""
        if cls is not JSONPointer:
            raise InvalidJSONPointer(
                "JSONPointer may only be specialized from the base class"
            )
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

    def to_last(
        self, doc: JSONValue
    ) -> tuple[JSONContainer[JSONValue], str | int | Literal["-"]]:
        return self._ptr.to_last(doc)  # type: ignore[no-any-return]  # JsonPointer is untyped

    def contains(self, other: "JSONPointer[Any]") -> bool:
        return self._ptr.contains(other._ptr)  # type: ignore[no-any-return]  # JsonPointer is untyped

    def validate_pointed_value(self, value: Any) -> _T_co:
        adapter = type(self)._init_adapter()
        try:
            return adapter.validate_python(value, strict=True)
        except Exception as e:
            raise PatchApplicationError(
                f"value {value!r} is not assignable to {self.__class__.__expected_type__!r} at pointer {str(self)!r}"
            ) from e
