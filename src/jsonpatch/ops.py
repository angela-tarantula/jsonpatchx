import json
from typing import Annotated, Any, Iterable, Literal, Protocol, Type, TypeAlias, Union, get_args, get_origin, LiteralString

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import BaseModel, Field, GetCoreSchemaHandler, TypeAdapter
from pydantic_core import core_schema


class JsonPointerValidator(JsonPointer):
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


class PatchOpBase(BaseModel):
    """Base for all patch operations."""

    pass


class AddOp(PatchOpBase):
    op: Literal["add"] = "add"
    path: JsonPointerType
    value: Annotated[Any, JsonValueType]

c = AddOp(path="/", value=3)

class RemoveOp(PatchOpBase):
    op: Literal["remove"] = "remove"
    path: JsonPointerType


class ReplaceOp(PatchOpBase):
    op: Literal["replace"] = "replace"
    path: JsonPointerType
    value: JsonValueType


class MoveOp(PatchOpBase):
    op: Literal["move"] = "move"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType


class CopyOp(PatchOpBase):
    op: Literal["copy"] = "copy"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType


class TestOp(PatchOpBase):
    op: Literal["test"] = "test"
    path: JsonPointerType
    value: JsonValueType


BuiltinOpUnion: TypeAlias = Annotated[
    Union[AddOp, RemoveOp, ReplaceOp, MoveOp, CopyOp, TestOp],
    Field(discriminator="op"),
]

BuiltinOpAdapter: TypeAdapter[BuiltinOpUnion] = TypeAdapter(BuiltinOpUnion)
BuiltinPatchAdapter: TypeAdapter[list[BuiltinOpUnion]] = TypeAdapter(
    list[BuiltinOpUnion]
)



class InvalidPatchSchema(Exception):
    """Raised when PatchSchema is constructed with invalid op models."""



class PatchSchema:
    """
    A JSON Patch schema defined by a set of Pydantic models
    discriminated by their 'op' Literal field.
    """

    def __init__(self, *op_models: Type[PatchOpBase]) -> None:
        if not op_models:
            raise InvalidPatchSchema("PatchSchema requires at least one op model")

        # Map op literal -> model to detect collisions
        op_value_to_model: dict[str, Type[PatchOpBase]] = {}

        for model in op_models:
            # 1. Ensure 'op' field exists
            try:
                field = model.model_fields["op"]  # pydantic v2
            except KeyError:
                raise InvalidPatchSchema(
                    f"{model.__name__} has no 'op' field; "
                    "each operation model must define op: Literal[...]"
                )

            # 2. Ensure annotation is Literal[...]
            annotation = field.annotation
            origin = get_origin(annotation)
            is_literal = (origin is not None) and (origin.__qualname__ == "Literal")
            if not is_literal:
                raise InvalidPatchSchema(
                    f"{model.__name__}.op must be typing.Literal[...] "
                    f"(got {annotation!r})"
                )

            # 3. Extract Literal values and ensure they are unique strings
            literal_values = get_args(annotation)
            if not literal_values:
                raise InvalidPatchSchema(
                    f"{model.__name__}.op Literal must have at least one value"
                )

            for value in literal_values:
                if not isinstance(value, str):
                    raise InvalidPatchSchema(
                        f"{model.__name__}.op Literal values must be str; "
                        f"got {value!r} (type {type(value)})"
                    )

                if value in op_value_to_model:
                    other = op_value_to_model[value]
                    raise InvalidPatchSchema(
                        "Duplicate op literal "
                        f"{value!r} in {model.__name__} and {other.__name__}"
                    )

                op_value_to_model[value] = model

        # If we get here, the schema is consistent.
        # Build the discriminated union and adapters.
        union_type: TypeAlias = Annotated[  # type: ignore[valid-type] # I know what I'm doing
            Union[tuple(op_models)],
            Field(discriminator="op"),
        ]
        self._op_adapter: TypeAdapter[union_type] = TypeAdapter(union_type)
        self._patch_adapter: TypeAdapter[union_type] = TypeAdapter(list[union_type])

    def parse_op(self, raw: dict[str, Any]) -> PatchOpBase:
        """Validate & coerce a single operation dict."""
        return self._op_adapter.validate_python(raw)

    def parse_patch(self, raw: Iterable[dict[str, Any]]) -> list[PatchOpBase]:
        """Validate & coerce a list of operation dicts."""
        return self._patch_adapter.validate_python(list(raw))




if __name__ == "__main__":
    raw = {"op": "add", "path": "/4", "value": "bar"}
    op = BuiltinOpAdapter.validate_python(raw)
    raw_patch = [
        {"op": "add", "path": "/foo", "value": "bar"},
        {"op": "remove", "path": "/foo"},
    ]

    ops = BuiltinPatchAdapter.validate_python(raw_patch)
    # -> list[AddOp | RemoveOp | ...]
