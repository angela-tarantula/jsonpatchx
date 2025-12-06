import json
from typing import Annotated, Any, TypeAlias

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import GetCoreSchemaHandler
from pydantic_core import core_schema


class JsonPointerValidator:
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
    def _validate(cls, v: str) -> JsonPointer:
        try:
            return JsonPointer(v)
        except JsonPointerException as e:
            raise ValueError(f"Invalid JSON Pointer: {v!r}") from e


class JsonValueValidator:
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


# Tell mypy that JsonPointerType is a str or a JsonPointer, but tell Pydantic to coerce it use JsonPointerValidator
JsonPointerType: TypeAlias = Annotated[str | JsonPointer, JsonPointerValidator]
# Tell mypy JsonValueType can be any object, but tell Pydantic to use JsonValueValidator
JsonValueType: TypeAlias = Annotated[Any, JsonValueValidator]
