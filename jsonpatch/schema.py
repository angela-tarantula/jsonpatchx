from abc import ABC, abstractmethod
from inspect import isabstract, isclass
from types import MappingProxyType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Iterable,
    Literal,
    Mapping,
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
    """
    The base class for declarative JSON Patch operation schemas,
    represented as strongly-typed Pydantic models.
    """

    _op_literals: ClassVar[tuple[str]]

    @override
    def __init_subclass__(cls, **kwargs: Unpack[ConfigDict]) -> None:
        """Validate the operation schema."""
        super().__init_subclass__(**kwargs)
        if not cls._is_annotated_correctly():
            raise InvalidOperationSchema(
                f"'{cls.__name__}'.op field requires Literal[str, ...] annotation"
            )
        cls._op_literals = get_args(cls.__annotations__["op"])

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
    A JSON Patch schema defined by a set of OperationSchema Pydantic models
    discriminated by their 'op' Literal field.
    """

    def __init__(self, *op_models: Type[OperationSchema]) -> None:
        self._validate_models(*op_models)
        self._model_map = self._build_model_map(*op_models)

        union_type, op_adapter, patch_adapter = self._build_adapters(*op_models)
        self._op_adapter = op_adapter
        self._patch_adapter = patch_adapter
        self._union_type = union_type  # For introspection/debugging

    @staticmethod
    def _validate_models(*op_models: Type[OperationSchema]) -> None:
        """Confirm all OperationSchemas are instantiable for dispatching."""
        if not op_models:
            raise InvalidPatchSchema(
                "PatchSchema requires at least one OperationSchema"
            )
        if not all(
            isclass(m) and issubclass(m, OperationSchema) and not isabstract(m)
            for m in op_models
        ):
            raise InvalidPatchSchema(
                "PatchSchema expects concrete OperationSchema subclasses"
            )

    @staticmethod
    def _build_model_map(
        *op_models: Type[OperationSchema],
    ) -> Mapping[str, Type[OperationSchema]]:
        """Build a mapping of op name -> model. Ensure all identifiers are disjoint."""
        model_map: dict[str, Type[OperationSchema]] = {}

        for model in op_models:
            for op_literal in model._op_literals:
                if op_literal in model_map:
                    other = model_map[op_literal]
                    raise InvalidPatchSchema(
                        f"{model.__name__} and {other.__name__} cannot share '{op_literal}' as an op identifier"
                    )
                model_map[op_literal] = model
        return MappingProxyType(model_map)

    @staticmethod
    def _build_adapters(
        *op_models: Type[OperationSchema],
    ) -> tuple[
        TypeAlias, TypeAdapter[OperationSchema], TypeAdapter[list[OperationSchema]]
    ]:
        """
        Build the discriminated union and Pydantic adapters for parsing ops and patches.

        Suppresses type-checker complaints because the Annotated union is a runtime-defined alias.
        """
        union_type: TypeAlias = Annotated[  # type: ignore[valid-type]
            Union[tuple(op_models)], Field(discriminator="op")
        ]
        op_adapter: TypeAdapter[OperationSchema] = TypeAdapter(union_type)
        patch_adapter: TypeAdapter[list[OperationSchema]] = TypeAdapter(
            list[union_type]
        )
        return union_type, op_adapter, patch_adapter

    def parse_op(self, raw: dict[str, Any]) -> OperationSchema:
        """Validate & coerce a single operation dict."""
        return self._op_adapter.validate_python(raw)

    def parse_patch(self, raw: Iterable[dict[str, Any]]) -> list[OperationSchema]:
        """Validate & coerce a list of operation dicts."""
        return self._patch_adapter.validate_python(list(raw))
