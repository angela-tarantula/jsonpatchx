from abc import ABC  # , abstractmethod
from typing import (
    Annotated,
    Any,
    Iterable,
    Literal,
    Type,
    TypeAlias,
    Union,
    get_args,
    get_origin,
)

from pydantic import BaseModel, Field, TypeAdapter

from jsonpatch.exceptions import InvalidOperationSchema, InvalidPatchSchema


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

        # 2. Ensure op is Literal[...]
        if origin is not Literal:
            raise InvalidOperationSchema(
                f"{cls.__name__}.op must be typing.Literal[...], got {op_anno!r}"
            )

        # 3. Ensure at least one literal value is specified
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

    @classmethod
    def names(cls) -> tuple[str, ...]:
        ann = getattr(cls, "__annotations__", {})
        op_anno = ann["op"]
        return get_args(op_anno)

    # @abstractmethod
    # def apply(self, doc: JsonValueType) -> JsonValueType:
    #     """Apply this operation to a JSON document."""


class PatchSchema:
    """
    A JSON Patch schema defined by a set of Pydantic models
    discriminated by their 'op' Literal field.
    """

    def __init__(self, *op_models: Type[OperationSchema]) -> None:
        if not op_models:
            raise InvalidPatchSchema("PatchSchema requires at least one op model")

        # Ensure the sets of OperationSchema identifiers are disjoint
        op_value_to_model: dict[str, Type[OperationSchema]] = {}
        for model in op_models:
            for name in model.names():
                other_model = op_value_to_model.get(name)
                if other_model:
                    raise InvalidPatchSchema(
                        f"{model.__name__} and {other_model.__name__} cannot share {name!r} as an op identifier"
                    )
                op_value_to_model[name] = model

        # If we get here, the PatchSchema is consistent.
        # Build the discriminated union and adapters.
        union_type: TypeAlias = Annotated[  # type: ignore[valid-type] # I know what I'm doing
            Union[tuple(op_models)],
            Field(discriminator="op"),
        ]
        try:
            self._op_adapter: TypeAdapter[union_type] = TypeAdapter(union_type)
        except Exception as e:
            raise InvalidPatchSchema(
                f"Duplicate op literal in models {', '.join(m.__name__ for m in op_models)}"
            ) from e
        self._patch_adapter: TypeAdapter[list[union_type]] = TypeAdapter(
            list[union_type]
        )

        # Enable introspection (for debugging, generating docs/tooling, etc)
        self._union_type = union_type
        self._op_models = list(op_models)
        self._op_map = op_value_to_model

    def parse_op(self, raw: dict[str, Any]) -> OperationSchema:
        """Validate & coerce a single operation dict."""
        return self._op_adapter.validate_python(raw)

    def parse_patch(self, raw: Iterable[dict[str, Any]]) -> list[OperationSchema]:
        """Validate & coerce a list of operation dicts."""
        return self._patch_adapter.validate_python(list(raw))
