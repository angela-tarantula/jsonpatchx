from collections.abc import Mapping, Sequence, Set
from inspect import isabstract, isclass
from types import MappingProxyType
from typing import Annotated, ClassVar, Literal, Self, TypeAliasType, Union, override

from pydantic import Field, TypeAdapter

from jsonpatch.builtins import STANDARD_OPS
from jsonpatch.exceptions import InvalidOperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.types import (
    _DEFAULT_POINTER_CLS,
    _POINTER_BACKEND_CTX_KEY,
    JSONValue,
    PointerBackend,
    _json_pointer_for,
)


class OperationRegistry:
    """
    A registry of JSON Patch operations, backed by OperationSchema subclasses.

    - Maps 'op' identifiers to OperationSchema types
    - Builds a discriminated union for validation / OpenAPI
    """

    __slots__ = (
        "_model_map",
        "_op_adapter",
        "_patch_adapter",
        "_union_type",
        "_pointer_cls",
    )
    _standard: ClassVar[Self | None] = None

    def __init__(
        self,
        *op_schemas: type[OperationSchema],
        pointer_cls: type[PointerBackend] = _DEFAULT_POINTER_CLS,
    ) -> None:
        self._validate_models(*op_schemas)
        self._model_map = self._build_model_map(*op_schemas)

        # validate pointer_cls with path="" as a probe
        _ = _json_pointer_for(path="", pointer_cls=pointer_cls)
        self._pointer_cls = pointer_cls

        union_type, op_adapter, patch_adapter = self._build_adapters(*op_schemas)
        self._union_type = union_type
        self._op_adapter = op_adapter
        self._patch_adapter = patch_adapter

    @staticmethod
    def _validate_models(*op_schemas: type[OperationSchema]) -> None:
        """Confirm all OperationSchemas are instantiable for dispatching."""
        if not op_schemas:
            raise InvalidOperationRegistry("At least one OperationSchema is required")
        for op in op_schemas:
            if not isclass(op):
                raise InvalidOperationRegistry(f"{op!r} is not a class")
            if not issubclass(op, OperationSchema):
                raise InvalidOperationRegistry(f"{op!r} is not an OperationSchema")
            if isabstract(op):
                raise InvalidOperationRegistry(f"{op!r} cannot be abstract")

    @staticmethod
    def _build_model_map(
        *op_schemas: type[OperationSchema],
    ) -> Mapping[str, type[OperationSchema]]:
        """Build a mapping of op name -> model. Ensure all identifiers are disjoint."""
        model_map: dict[str, type[OperationSchema]] = {}
        for model in op_schemas:
            for op_literal in model._op_literals:
                if op_literal in model_map:
                    other = model_map[op_literal]
                    raise InvalidOperationRegistry(
                        f"{model.__name__} and {other.__name__} cannot share "
                        f"'{op_literal}' as an op identifier"
                    )
                model_map[op_literal] = model
        return MappingProxyType(model_map)

    @staticmethod
    def _build_adapters(
        *op_schemas: type[OperationSchema],
    ) -> tuple[
        TypeAliasType,
        TypeAdapter[OperationSchema],
        TypeAdapter[list[OperationSchema]],
    ]:
        """
        Build the discriminated union and Pydantic adapters for parsing ops and patches.
        """
        type union_type = Annotated[  # type: ignore[valid-type] # dynamic runtime type for Pydantic
            Union[tuple(op_schemas)], Field(discriminator="op")
        ]
        op_adapter: TypeAdapter[OperationSchema] = TypeAdapter(union_type)
        patch_adapter: TypeAdapter[list[OperationSchema]] = TypeAdapter(
            list[union_type]
        )
        return union_type, op_adapter, patch_adapter

    @property
    def ops_by_name(self) -> Mapping[str, type[OperationSchema]]:
        """The mapping of each operation identifier to its operation schema."""
        return self._model_map

    @property
    def ops(self) -> Set[type[OperationSchema]]:
        """The operation schemas that this registry recognizes."""
        return frozenset(self._model_map.values())

    @property
    def union(self) -> TypeAliasType:
        """The discriminated union type of all operation schemas."""
        return self._union_type

    @property
    def _ctx(self) -> dict[Literal["jsonpatch:pointer_backend"], type[PointerBackend]]:
        return {_POINTER_BACKEND_CTX_KEY: self._pointer_cls}

    def parse_python_op(
        self, obj: Mapping[str, JSONValue] | OperationSchema
    ) -> OperationSchema:
        """
        Validate & coerce a single operation dict.

        Example python: {"op": "remove", "path": "/foo/bar"}
        """
        return self._op_adapter.validate_python(
            obj,
            strict=True,
            by_alias=True,
            by_name=False,
            extra="forbid",
            context=self._ctx,
        )

    def parse_python_patch(
        self, python: Sequence[Mapping[str, JSONValue]] | Sequence[OperationSchema]
    ) -> list[OperationSchema]:
        """
        Validate & coerce a sequence of operation dicts.

        Example python: [{"op": "remove", "path": "/foo/bar"}, {"op": "add", "path": "/baz", "value": 42}]
        """
        return self._patch_adapter.validate_python(
            python,
            strict=True,
            by_alias=True,
            by_name=False,
            extra="forbid",
            context=self._ctx,
        )

    def parse_json_op(self, text: str | bytes | bytearray) -> OperationSchema:
        """
        Validate & coerce a single JSON-serialized OperationSchema.

        Example text: '{"op": "remove", "path": "/foo/bar"}'
        """
        return self._op_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
            extra="forbid",
            context=self._ctx,
        )

    def parse_json_patch(self, text: str | bytes | bytearray) -> list[OperationSchema]:
        """
        Validate & coerce a JSON Patch.

        Example text: '[{"op": "remove", "path": "/foo/bar"}, {"op": "add", "path": "/baz", "value": 42}]'
        """
        return self._patch_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
            extra="forbid",
            context=self._ctx,
        )

    @override
    def __repr__(self) -> str:
        ops = ", ".join(m.__name__ for m in self.ops)
        return f"{self.__class__.__name__}({ops})"

    @classmethod
    def standard(cls) -> Self:
        """Standard RFC 6902 ops."""
        if cls._standard is None:
            cls._standard = cls(*STANDARD_OPS)
        return cls._standard

    @classmethod
    def with_standard(
        cls,
        *extra_ops: type[OperationSchema],
        pointer_cls: type[PointerBackend] = _DEFAULT_POINTER_CLS,
    ) -> Self:
        """Built-in RFC 6902 ops, plus extras."""
        return cls(*STANDARD_OPS, *extra_ops, pointer_cls=pointer_cls)

    @override
    def __hash__(self) -> int:
        # Hashing is best-effort, user-defined ops may be unhashable.
        return hash((self.__class__, self._pointer_cls, self.ops))


if __name__ == "__main__":
    raw = {"op": "add", "path": "/4", "value": "bar"}

    op = OperationRegistry.standard().parse_python_op(raw)
    raw_patch = [
        {"op": "move", "path": "/foo", "from": "/bar"},
        {"op": "add", "path": "/bar", "value": "baz"},
        {"op": "add", "path": "/bar", "value": "baz"},
    ]
    ops = OperationRegistry.standard().parse_python_patch(raw_patch)
