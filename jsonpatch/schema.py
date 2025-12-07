import inspect
from abc import ABC, abstractmethod
from typing import (
    Annotated,
    Any,
    ClassVar,
    Iterable,
    Literal,
    Type,
    TypeAlias,
    Union,
    Unpack,
    cast,
    get_args,
    get_origin,
    override,
)

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from jsonpatch.exceptions import InvalidOperationSchema, InvalidPatchSchema
from jsonpatch.types import JsonValueType


class OperationSchema(BaseModel, ABC):
    """Base for all patch operations."""

    _op_identifiers: ClassVar[tuple[str]]

    @override
    def __init_subclass__(cls, **kwargs: Unpack[ConfigDict]) -> None:
        """Validate the operation schema."""
        super().__init_subclass__(**kwargs)
        if not cls._is_annotated_correctly():
            raise InvalidOperationSchema(
                f"'{cls.__name__}'.op field requires Literal[str, ...] annotation"
            )
        cls._op_identifiers = get_args(cls.__annotations__["op"])

    @classmethod
    def _is_annotated_correctly(cls) -> bool:
        """Confirms 'op' field is annotated as Literal[str, ...]"""
        return bool(
            (op_anno := cls.__annotations__.get("op"))  # op is annotated
            and (cast(object, get_origin(op_anno)) is Literal)  # op is Literal
            and bool(literal_vals := get_args(op_anno))  # op is Literal[...]
            and all(isinstance(v, str) for v in literal_vals)  # op is Literal[str, ...]
        )

    @abstractmethod
    def apply(self, doc: JsonValueType) -> JsonValueType:
        """Apply this operation to a JSON document."""
        ...


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
                raise InvalidPatchSchema(
                    f"{typing_expectation}, but received an instance of type '{type(m).__name__}': {m!r}"
                )
            if not issubclass(m, OperationSchema):
                raise InvalidPatchSchema(
                    f"{typing_expectation}, but received an unrelated class '{m.__name__}'."
                )
            if inspect.isabstract(m):
                missing = ", ".join(sorted(m.__abstractmethods__))
                raise InvalidPatchSchema(
                    f"{typing_expectation}, but received an abstract class '{m.__name__}'. Missing implementations for: {missing}."
                )

        # Ensure the sets of OperationSchema identifiers are disjoint
        _model_map: dict[str, Type[OperationSchema]] = {}
        for model in op_models:
            for op in model._op_identifiers:
                other_model = _model_map.get(op)
                if other_model:
                    raise InvalidPatchSchema(
                        f"{model.__name__} and {other_model.__name__} cannot share '{op}' as an op identifier"
                    )
                _model_map[op] = model

        # If we get here, the PatchSchema is consistent. Build the discriminated union and adapters.
        # Suppress errors because we know we're creating dynamic runtime TypeAlias.
        union_type: TypeAlias = Annotated[  # type: ignore[valid-type]
            Union[tuple(op_models)], Field(discriminator="op")
        ]
        self._op_adapter: TypeAdapter[OperationSchema] = TypeAdapter(union_type)
        self._patch_adapter: TypeAdapter[list[OperationSchema]] = TypeAdapter(
            list[union_type]
        )

        # Stash these to enable introspection (for debugging, generating docs/tooling, etc)
        self._union_type = union_type
        self._op_models = list(op_models)
        self._model_map = _model_map

    def parse_op(self, raw: dict[str, Any]) -> OperationSchema:
        """Validate & coerce a single operation dict."""
        return self._op_adapter.validate_python(raw)

    def parse_patch(self, raw: Iterable[dict[str, Any]]) -> list[OperationSchema]:
        """Validate & coerce a list of operation dicts."""
        return self._patch_adapter.validate_python(list(raw))
