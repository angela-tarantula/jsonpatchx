import json
from typing import Annotated, Any

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema

from jsonpatch.exceptions import OperationValidationError


class PydanticJsonPointer:
    """Pydantic-aware wrapper for jsonpointer.JsonPointer."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        # Parse from string, return a JsonPointer instance, and serialize back to string for JSON
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize,
                return_schema=core_schema.str_schema(),
                when_used="json",
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: core_schema.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        """Advertise JsonPointer as a string with a helpful format marker."""
        json_schema = handler(core_schema)
        json_schema.update({"format": "json-pointer"})
        return json_schema

    @classmethod
    def _validate(cls, v: str | JsonPointer) -> JsonPointer:
        if isinstance(v, JsonPointer):
            return v
        try:
            return JsonPointer(v)
        except JsonPointerException as e:
            raise OperationValidationError(f"Invalid JSON Pointer: {v!r}") from e

    @classmethod
    def _serialize(cls, v: JsonPointer) -> str:
        return str(v)


class PydanticJsonValue:
    """Any JSON-serializable value."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.any_schema(),
        )

    @classmethod
    def _validate(cls, v: object) -> object:
        try:
            json.dumps(v)
        except (TypeError, ValueError) as e:
            raise OperationValidationError(
                f"Value is not JSON-serializable: {v!r}"
            ) from e
        return v


class PydanticJsonText:
    """Any JSON-formatted text."""

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
    def _validate(cls, v: str | bytes | bytearray) -> str | bytes | bytearray:
        try:
            json.loads(v)
        except (TypeError, ValueError) as e:
            raise OperationValidationError(
                f"String is not JSON-formatted: {v!r}"
            ) from e
        return v


# Tell mypy that JsonPointerType is a str or a JsonPointer, but tell Pydantic to coerce it use PydanticJsonPointer to coerce
type JsonPointerType = Annotated[str | JsonPointer, PydanticJsonPointer]

# Tell mypy JsonValueType can be any object, but tell Pydantic to use PydanticJsonValue to validate
type JsonValueType = Annotated[object, PydanticJsonValue]

# Tell mypy JsonTextType can be json text type, but tell Pydantic to use PydanticJsonText to validate
type JsonTextType = Annotated[str | bytes | bytearray, PydanticJsonText]
