from inspect import isabstract, isclass
from types import MappingProxyType
from typing import (
    Annotated,
    Any,
    Iterable,
    Mapping,
    Self,
    Type,
    TypeAlias,
    Union,
)

from pydantic import Field, TypeAdapter

from jsonpatch.exceptions import InvalidPatchSchema
from jsonpatch.operation_schema import OperationSchema
from jsonpatch.ops_builtin import AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp


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

    @property
    def op_map(self) -> Mapping[str, Type[OperationSchema]]:
        """The mapping of each operation identifier to its operation schema."""
        return self._model_map

    @property
    def op_models(self) -> tuple[Type[OperationSchema], ...]:
        """The operation schemas that this patch schema recognizes."""
        return tuple(self._model_map.values())

    @property
    def op_union_type(self) -> TypeAlias:
        """The discriminated union type of all operation schemas."""
        return self._union_type

    def parse_op(self, raw: dict[str, Any]) -> OperationSchema:
        """Validate & coerce a single operation dict."""
        return self._op_adapter.validate_python(raw)

    def parse_patch(self, raw: Iterable[dict[str, Any]]) -> list[OperationSchema]:
        """Validate & coerce a list of operation dicts."""
        return self._patch_adapter.validate_python(list(raw))

    @classmethod
    def with_defaults(cls, *extra_ops: Type[OperationSchema]) -> Self:
        return cls(AddOp, RemoveOp, ReplaceOp, MoveOp, CopyOp, TestOp, *extra_ops)


if __name__ == "__main__":
    raw = {"op": "add", "path": "/4", "value": "bar"}

    op = PatchSchema.with_defaults().parse_op(raw)
    raw_patch = [
        {"op": "add", "path": "/foo", "value": "bar"},
        {"op": "remove", "path": "/foo"},
    ]
    ops = PatchSchema.with_defaults().parse_patch(raw_patch)
