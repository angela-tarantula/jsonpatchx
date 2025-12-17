from __future__ import annotations

import json
from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence
from typing import Annotated, Any, TypeVar

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema

from jsonpatch.exceptions import InvalidOperationSchema


class PydanticJsonTextValidator:
    """Pydantic-aware wrapper for JSON-formatted text."""

    TEXT = TypeVar("TEXT", str, bytes, bytearray)

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[object],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.union_schema(
                [core_schema.str_schema(), core_schema.bytes_schema()]
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, object]:
        """Expose JSON text as a string with a 'json' format hint."""
        json_schema = handler(core_schema)
        # OpenAPI can't really express bytes/bytearray here, so describe the most common representation
        json_schema.update({"type": "string", "format": "json"})
        return json_schema

    @classmethod
    def _validate(cls, v: TEXT) -> TEXT:
        try:
            json.loads(v)
        except (TypeError, ValueError) as e:
            raise InvalidOperationSchema(
                f"{type(v).__class__.__name__} is not JSON-formatted: {v!r}"
            ) from e
        return v


class PydanticJsonValueValidator:
    """Pydantic-aware wrapper for any JSON-serializable value."""

    VALUE = TypeVar("VALUE")

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
    def _validate(cls, v: VALUE) -> VALUE:
        # Forbid NaN because it's not valid JSON
        try:
            json.dumps(
                v, allow_nan=False
            )  # TODO: use orjson? it turns out {"4":4, 4:3} can dump to '{"4": 4, "4": 3}'
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
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.union_schema(
                [core_schema.int_schema(), core_schema.float_schema()]
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        json_schema = handler(schema)
        json_schema.update(
            {"description": "number (int|float)"}  # TODO: anything else?
        )
        return json_schema

    @classmethod
    def _validate(cls, v: object) -> int | float:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise InvalidOperationSchema(
                f"Expected JSON number (int|float), not {v.__class__.__name__}: {v!r}"
            )
        return v


# Core JSON type aliases

type JSONText = Annotated[str | bytes | bytearray, PydanticJsonTextValidator]

type JSONBoolean = bool
type JSONNumber = int | float  # TODO: don't let pydantic coerce bool to int
type JSONString = str
type JSONNull = None
type JSONPrimitive = JSONBoolean | JSONNumber | JSONString | JSONNull

type JSONArray = Sequence[JSONValue]
type JSONObject = Mapping[str, JSONValue]

type JSONValue = Annotated[
    JSONPrimitive | JSONArray | JSONObject, PydanticJsonValueValidator
]

type MutableJSONArray = MutableSequence[JSONValue]
type MutableJSONObject = MutableMapping[str, JSONValue]


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


type JSONPointer = Annotated[str, PydanticJsonPointerValidator]
