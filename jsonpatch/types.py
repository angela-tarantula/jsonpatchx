from __future__ import annotations

import json
from typing import Annotated, Any, MutableMapping, MutableSequence

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema

from jsonpatch.exceptions import InvalidOperationSchema


class PydanticJsonPointerValidator:
    """Pydantic-aware wrapper for jsonpointers."""

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
        """Expose JSONPointer as a string with a 'json-pointer' format hint."""
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


class PydanticJsonTextValidator:
    """A Pydantic-aware wrapper for JSON-formatted text."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
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
        cls,
        core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        """Expose JSONText as a string with a 'json' format hint."""
        json_schema = handler(core_schema)
        # OpenAPI can't really express bytes/bytearray here, so describe the most common representation
        json_schema.update({"type": "string", "format": "json"})
        return json_schema

    @classmethod
    def _validate(cls, v: str | bytes | bytearray) -> str | bytes | bytearray:
        try:
            json.loads(v)
        except (TypeError, ValueError) as e:
            raise InvalidOperationSchema(f"String is not JSON-formatted: {v!r}") from e
        return v


class PydanticJsonValueValidator:
    """A Pydantic-aware wrapper for any JSON-serializable value."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        # Use a very permissive schema at the core level and let the validator enforce JSON-serializability
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
    def _validate(cls, v: object) -> object:
        try:
            json.dumps(v, allow_nan=False) # TODO: use orjson! it turns out {4:4, "4":4} can dump to '{"4": 4, "4": 3}'
        except (TypeError, ValueError) as e:
            raise InvalidOperationSchema(
                f"Value is not JSON-serializable: {v!r}"
            ) from e
        return v


# Core types

type JSONPointer = Annotated[str, PydanticJsonPointerValidator]
type JSONText = Annotated[str | bytes | bytearray, PydanticJsonTextValidator]

type JSONBoolean = bool
type JSONString = str
type JSONNull = None
type JSONNumber = int | float
type JSONArray = MutableSequence[JSONValue]
type JSONObject = MutableMapping[str, JSONValue]

type JSONValue = Annotated[
    JSONBoolean | JSONNumber | JSONString | JSONNull | JSONArray | JSONObject,
    PydanticJsonValueValidator,
]
