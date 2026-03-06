from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from inspect import isabstract, isclass
from types import MappingProxyType
from typing import (
    Annotated,
    Any,
    ClassVar,
    Generic,
    TypeAliasType,
    TypeVarTuple,
    Union,
)

from pydantic import Field, TypeAdapter

from jsonpatchx.builtins import (
    STANDARD_OPS,
    AddOp,
    CopyOp,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
from jsonpatchx.exceptions import InvalidOperationRegistry, OperationNotRecognized
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue

type AnyRegistry = OperationRegistry[*tuple[Any, ...]]
Ops = TypeVarTuple("Ops")


class OperationRegistry(Generic[*Ops]):
    """
    Registry for JSON Patch operation types.

    >>> type LeastPrivilegedRegistry = OperationRegistry[TestOp, IncrementOp]
    >>> type MorePrivilegedRegistry = OperationRegistry[TestOp, SetIntegerOp]
    >>> type StringRegistry = OperationRegistry[ConcatenateOp, ReplaceSubstringOp, IncrementStringOp]
    """

    ops: ClassVar[tuple[type[OperationSchema], ...]]
    union: ClassVar[TypeAliasType]
    _ops_set: ClassVar[frozenset[type[OperationSchema]]]
    _model_map: ClassVar[Mapping[str, type[OperationSchema]]]
    _op_adapter: ClassVar[TypeAdapter[OperationSchema]]
    _patch_adapter: ClassVar[TypeAdapter[list[OperationSchema]]]

    def __new__(cls, *_: object, **__: object) -> OperationRegistry[*Ops]:
        raise TypeError(
            f"{cls.__name__} is a registry type and cannot be instantiated. "
            "Use it directly via OperationRegistry[Op1, Op2, ...]."
        )

    def __class_getitem__(cls, args: object) -> type[AnyRegistry]:
        # normalize
        params: tuple[object, ...] = args if isinstance(args, tuple) else (args,)

        # parse
        op_models = cls._validate_op_models(params)
        cls._validate_op_name_uniqueness(*op_models)
        ordered_ops = cls._deterministic_sort(*op_models)

        # build
        model_map = cls._build_model_map(*ordered_ops)
        union_type, op_adapter, patch_adapter = cls._build_adapters(*ordered_ops)

        # subtype
        name = cls._registry_type_name(ordered_ops)
        namespace = {
            "ops": ordered_ops,
            "_ops_set": frozenset(ordered_ops),
            "union": union_type,
            "_model_map": model_map,
            "_op_adapter": op_adapter,
            "_patch_adapter": patch_adapter,
        }
        registry_type = type(name, (cls,), namespace)
        return registry_type

    @staticmethod
    def _registry_type_name(ops: tuple[type[OperationSchema], ...]) -> str:
        if ops == OperationRegistry._deterministic_sort(*STANDARD_OPS):
            return "StandardRegistry"
        op_names = "_".join(op.__name__ for op in ops)
        return f"OperationRegistry_{op_names}"

    @staticmethod
    def _validate_op_models(
        params: tuple[object, ...],
    ) -> tuple[type[OperationSchema], ...]:
        if not params:
            raise InvalidOperationRegistry(
                "OperationRegistry requires at least one operation model"
            )

        validated = tuple(
            OperationRegistry._validate_op_model(param) for param in params
        )
        return validated

    @staticmethod
    def _validate_op_model(param: object) -> type[OperationSchema]:
        if not isclass(param):
            raise InvalidOperationRegistry(f"{param!r} is not a class")
        if not issubclass(param, OperationSchema) or isabstract(param):
            raise InvalidOperationRegistry(
                f"{param!r} is not a concrete OperationSchema"
            )
        return param

    @staticmethod
    def _validate_op_name_uniqueness(*op_models: type[OperationSchema]) -> None:
        duplicates = {
            name
            for name, count in Counter(model.__name__ for model in op_models).items()
            if count > 1
        }
        if duplicates:
            raise InvalidOperationRegistry(
                "Expected unique OperationSchema names, got duplicates for these: "
                f"{duplicates!r}"
            )

    @staticmethod
    def _build_model_map(
        *op_models: type[OperationSchema],
    ) -> Mapping[str, type[OperationSchema]]:
        model_map: dict[str, type[OperationSchema]] = {}
        for model in op_models:
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
        *op_models: type[OperationSchema],
    ) -> tuple[
        TypeAliasType,
        TypeAdapter[OperationSchema],
        TypeAdapter[list[OperationSchema]],
    ]:
        ordered_ops_tuple: tuple[type[OperationSchema], ...] = (
            OperationRegistry._deterministic_sort(*op_models)
        )

        type RegistryPatchOperation = Annotated[
            Union[ordered_ops_tuple],  # type: ignore[valid-type]  # dynamic runtime type for Pydantic
            Field(discriminator="op"),
        ]
        op_adapter: TypeAdapter[OperationSchema] = TypeAdapter(RegistryPatchOperation)
        patch_adapter: TypeAdapter[list[OperationSchema]] = TypeAdapter(
            list[RegistryPatchOperation]
        )
        return RegistryPatchOperation, op_adapter, patch_adapter

    @staticmethod
    def _deterministic_sort(
        *op_models: type[OperationSchema],
    ) -> tuple[type[OperationSchema], ...]:
        """Deterministic sorting of OperationSchemas for OpenAPI reproducibility."""
        return tuple(sorted(op_models, key=lambda op: op._op_literals[0]))

    @classmethod
    def ops_by_name(cls) -> Mapping[str, type[OperationSchema]]:
        return cls._model_map

    @classmethod
    def ops_set(cls) -> frozenset[type[OperationSchema]]:
        return cls._ops_set

    @classmethod
    def parse_python_op(
        cls, obj: Mapping[str, JSONValue] | OperationSchema
    ) -> OperationSchema:
        if isinstance(obj, OperationSchema):
            if type(obj) not in cls._ops_set:
                raise OperationNotRecognized(
                    f"Operation {type(obj).__name__} is not allowed in this registry"
                )
            return obj
        return cls._op_adapter.validate_python(
            obj,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    @classmethod
    def parse_python_patch(
        cls, python: Sequence[OperationSchema | Mapping[str, JSONValue]]
    ) -> list[OperationSchema]:
        ops: list[OperationSchema] = []
        for item in python:
            if isinstance(item, OperationSchema):
                if type(item) not in cls._ops_set:
                    raise OperationNotRecognized(
                        f"Operation {type(item).__name__} is not allowed in this registry"
                    )
                ops.append(item)
            else:
                ops.append(
                    cls._op_adapter.validate_python(
                        item,
                        strict=True,
                        by_alias=True,
                        by_name=False,
                    )
                )
        return ops

    @classmethod
    def parse_json_op(cls, text: str | bytes | bytearray) -> OperationSchema:
        return cls._op_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    @classmethod
    def parse_json_patch(cls, text: str | bytes | bytearray) -> list[OperationSchema]:
        return cls._patch_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )


StandardRegistry = OperationRegistry[AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp]
