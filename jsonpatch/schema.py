import inspect
from abc import ABC  # , abstractmethod
from typing import (
    Annotated,
    Any,
    ClassVar,
    Iterable,
    Literal,
    Type,
    TypeAlias,
    Union,
    cast,
    get_args,
    get_origin,
)

from pydantic import BaseModel, Field, TypeAdapter

from jsonpatch.exceptions import InvalidOperationSchema, InvalidPatchSchema


class OperationSchema(BaseModel, ABC):
    """Base for all patch operations."""

    op: str

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate the operation schema."""
        super().__init_subclass__(**kwargs)

        ann = getattr(cls, "__annotations__", {})

        # 1. Ensure 'op' exists
        if "op" not in ann:
            raise InvalidOperationSchema(f"'{cls.__name__}' must define an 'op' field")

        op_anno = ann["op"]
        origin = get_origin(op_anno)

        # 2. Ensure op is Literal[...]
        if origin is not Literal:
            raise InvalidOperationSchema(
                f"'{cls.__name__!r}.op' must be typing.Literal[...], got {op_anno!r}"
            )

        # 3. Ensure at least one literal value is specified
        literal_values = get_args(op_anno)
        if not literal_values:
            raise InvalidOperationSchema(
                f"'{cls.__name__}.op' Literal must have at least one value"
            )

        # 4. Ensure every literal value is a string
        for value in literal_values:
            if not isinstance(value, str):
                raise InvalidOperationSchema(
                    f"'{cls.__name__}.op' Literal values must be str; "
                    f"got {value!r} (type {type(value)})"
                )

    @classmethod
    def _op_discriminators(cls) -> tuple[str, ...]:
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

        typing_expectation = "PatchSchema expects concrete OperationSchema classes"
        for m in op_models:
            if not inspect.isclass(m):
                raise TypeError(
                    f"{typing_expectation}, but received an instance of type '{type(m).__name__}': {m!r}"
                )
            if not issubclass(m, OperationSchema):
                raise TypeError(
                    f"{typing_expectation}, but received an unrelated class '{m.__name__}'."
                )
            if inspect.isabstract(m):
                missing = ", ".join(sorted(m.__abstractmethods__))
                raise TypeError(
                    f"{typing_expectation}, but received an abstract class '{m.__name__}'. Missing implementations for: {missing}."
                )

        # Ensure the sets of OperationSchema identifiers are disjoint
        _op_map: dict[str, Type[OperationSchema]] = {}
        for model in op_models:
            for op in model._op_discriminators():
                other_model = _op_map.get(op)
                if other_model:
                    raise InvalidPatchSchema(
                        f"{model.__name__} and {other_model.__name__} cannot share '{op}' as an op identifier"
                    )
                _op_map[op] = model

        # If we get here, the PatchSchema is consistent. Build the discriminated union and adapters.
        # Suppress errors because we know we're creating dynamic runtime TypeAlias.
        union_type: TypeAlias = Annotated[  # type: ignore[valid-type]
            Union[tuple(op_models)],  # pyright: ignore[reportInvalidTypeArguments, reportInvalidTypeForm]
            Field(discriminator="op"),
        ]
        self._op_adapter: TypeAdapter[OperationSchema] = TypeAdapter(union_type)
        self._patch_adapter: TypeAdapter[list[OperationSchema]] = TypeAdapter(
            list[union_type]
        )

        # Stash these to enable introspection (for debugging, generating docs/tooling, etc)
        self._union_type = union_type
        self._op_models = list(op_models)
        self._op_map = _op_map

    def parse_op(self, raw: dict[str, Any]) -> OperationSchema:
        """Validate & coerce a single operation dict."""
        return self._op_adapter.validate_python(raw)

    def parse_patch(self, raw: Iterable[dict[str, Any]]) -> list[OperationSchema]:
        """Validate & coerce a list of operation dicts."""
        return self._patch_adapter.validate_python(list(raw))
