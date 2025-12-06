import json
from typing import Annotated, Any, Iterable, Literal, Type, TypeAlias, Union, get_args, get_origin
from abc import ABC

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import BaseModel, Field, GetCoreSchemaHandler, TypeAdapter
from pydantic_core import core_schema

class InvalidOperationSchema(Exception):
    """Raised when OperationSchema is invalid."""

class InvalidPatchSchema(Exception):
    """Raised when PatchSchema is constructed with incompatible OperationSchemas."""



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


class OperationSchema(BaseModel, ABC):
    """Base for all patch operations."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate the operation schema."""
        super().__init_subclass__(**kwargs)

        ann = getattr(cls, "__annotations__", {})

        # 1. Ensure 'op' exists
        if "op" not in ann:
            raise InvalidOperationSchema(
                f"{cls.__name__} must define an 'op' field annotated as Literal[...]"
            )

        op_anno = ann["op"]
        origin = get_origin(op_anno)

        # 2. Ensure it's Literal[...]
        if origin is not Literal:
            raise InvalidOperationSchema(
                f"{cls.__name__}.op must be typing.Literal[...], "
                f"got {op_anno!r}"
            )

        # 3. Ensure there's at least one literal value
        literal_values = get_args(op_anno)
        if not literal_values:
            raise InvalidOperationSchema(
                f"{cls.__name__}.op Literal must have at least one value"
            )

        # 4. Ensure every literal value is a string
        for value in literal_values:
            if not isinstance(value, str):
                raise InvalidOperationSchema(
                    f"{cls.__name__}.op Literal values must be str; "
                    f"got {value!r} (type {type(value)})"
                )

        # 5. Ensure all "fields" have type hints
        for name, value in cls.__dict__.items():
            # Ignore private / dunder names
            if name.startswith("_"):
                continue

            # Skip descriptors/method-like things
            if isinstance(value, (classmethod, staticmethod, property)):
                continue

            # Skip callables (functions, classes, etc.)
            if callable(value):
                continue

            # Skip model_config
            if name == "model_config":
                continue

            # If it's not annotated, it's probably meant to be a field,
            # so we require a type hint.
            if name not in ann:
                raise InvalidOperationSchema(
                    f"{cls.__name__}.{name!r} must have a type annotation; "
                    "all operation fields must be typed"
                )


class AddOp(OperationSchema):
    op: Literal["add"] = "add"
    path: JsonPointerType
    value: JsonValueType

c = AddOp(path="/", value=3)

class RemoveOp(OperationSchema):
    op: Literal["remove"] = "remove"
    path: JsonPointerType


class ReplaceOp(OperationSchema):
    op: Literal["replace"] = "replace"
    path: JsonPointerType
    value: JsonValueType


class MoveOp(OperationSchema):
    op: Literal["move"] = "move"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType


class CopyOp(OperationSchema):
    op: Literal["copy"] = "copy"
    from_: JsonPointerType = Field(alias="from")
    path: JsonPointerType


class TestOp(OperationSchema):
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




class PatchSchema:
    """
    A JSON Patch schema defined by a set of Pydantic models
    discriminated by their 'op' Literal field.
    """

    def __init__(self, *op_models: Type[OperationSchema]) -> None:
        if not op_models:
            raise InvalidPatchSchema("PatchSchema requires at least one op model")

        # Map op literal -> model to detect collisions
        # op_value_to_model: dict[str, Type[OperationSchema]] = {}

        for model in op_models:
            # check that the sets of model op stringliterals are disjoint
            pass

        # If we get here, the schema is consistent.
        # Build the discriminated union and adapters.
        union_type: TypeAlias = Annotated[  # type: ignore[valid-type] # I know what I'm doing
            Union[tuple(op_models)],
            Field(discriminator="op"),
        ]
        self._op_adapter: TypeAdapter[union_type] = TypeAdapter(union_type)
        self._patch_adapter: TypeAdapter[list[union_type]] = TypeAdapter(list[union_type])

    def parse_op(self, raw: dict[str, Any]) -> OperationSchema:
        """Validate & coerce a single operation dict."""
        return self._op_adapter.validate_python(raw)

    def parse_patch(self, raw: Iterable[dict[str, Any]]) -> list[OperationSchema]:
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
