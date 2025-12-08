import json
from typing import Annotated, Any, TypeAlias

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema


class PydanticJsonPointer:
    """Pydantic-aware wrapper for jsonpointer.JsonPointer."""

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> core_schema.CoreSchema:
        # Parse from string, return a JsonPointer instance
        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.str_schema(),
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
            raise ValueError(f"Invalid JSON Pointer: {v!r}") from e


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
        except TypeError as e:
            raise ValueError(f"Value is not JSON-serializable: {v!r}") from e
        return v


# Tell mypy that JsonPointerType is a str or a JsonPointer, but tell Pydantic to coerce it use PydanticJsonPointer
JsonPointerType: TypeAlias = Annotated[str | JsonPointer, PydanticJsonPointer]
# Tell mypy JsonValueType can be any object, but tell Pydantic to use PydanticJsonValue
JsonValueType: TypeAlias = Annotated[Any, PydanticJsonValue]
