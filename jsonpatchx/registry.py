from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from functools import cached_property
from inspect import isabstract
from typing import (
    Annotated,
    Any,
    ClassVar,
    Generic,
    TypeAliasType,
    TypeVarTuple,
    Union,
    cast,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    model_validator,
)

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


class RegistrySpecs(BaseModel):
    """Derived registry artifacts for an ordered set of operation models.

    Attributes:
        ops: Operation models as supplied by the registry declaration.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    ops: tuple[type[OperationSchema], ...]

    @model_validator(mode="after")
    def _validate_ops(self) -> RegistrySpecs:
        """Validates non-empty, concrete, uniquely named/discriminated models."""

        if not self.ops:
            raise InvalidOperationRegistry(
                "OperationRegistry requires at least one operation model"
            )

        non_concrete_models = [
            model.__name__ for model in self.ops if isabstract(model)
        ]
        if non_concrete_models:
            raise InvalidOperationRegistry(
                "Expected concrete OperationSchema classes, got abstract models: "
                f"{sorted(non_concrete_models)!r}"
            )

        def duplicates(values: Iterable[str]) -> list[str]:
            """Returns sorted duplicate values for deterministic error output."""
            return sorted(
                {value for value, count in Counter(values).items() if count > 1}
            )

        dupe_names = duplicates(model.__name__ for model in self.ops)
        if dupe_names:
            raise InvalidOperationRegistry(
                "Expected unique OperationSchema names, got duplicates for these: "
                f"{dupe_names!r}"
            )

        dupe_op_literals = duplicates(
            op_literal for model in self.ops for op_literal in model._op_literals
        )
        if dupe_op_literals:
            raise InvalidOperationRegistry(
                f"Unable to discriminate by 'op' due to duplicates: {dupe_op_literals!r}"
            )

        return self

    @cached_property
    def ordered_ops(self) -> tuple[type[OperationSchema], ...]:
        """Deterministic operation order used for schema and adapter stability."""
        return tuple(sorted(self.ops, key=lambda op: op._op_literals[0]))

    @cached_property
    def model_map(self) -> Mapping[str, type[OperationSchema]]:
        """The mapping of each op literal to its owning operation model."""
        return {
            op_literal: model
            for model in self.ordered_ops
            for op_literal in model._op_literals
        }

    @cached_property
    def union(self) -> TypeAliasType:
        """The discriminated union type used for operation parsing."""
        type RegistryPatchOperation = Annotated[
            Union[self.ordered_ops],  # type: ignore[name-defined]
            Field(discriminator="op"),
        ]
        return RegistryPatchOperation

    @cached_property
    def op_adapter(self) -> TypeAdapter[OperationSchema]:
        """The Pydantic adapter for validating a single operation payload."""
        return TypeAdapter(self.union)

    @cached_property
    def patch_adapter(self) -> TypeAdapter[list[OperationSchema]]:
        """The Pydantic adapter for validating a full patch array payload."""
        return TypeAdapter(list[self.union])  # type: ignore[name-defined]

    @cached_property
    def is_RFC6902(self) -> bool:
        """Whether or not the operation set is RFC 6902."""
        return self.ordered_ops == _STANDARD_REGISTRY_SPECS.ordered_ops


_STANDARD_REGISTRY_SPECS = RegistrySpecs(ops=STANDARD_OPS)


class OperationRegistry(Generic[*Ops]):
    """
    Registry for JSON Patch operation types.

    >>> type LeastPrivilegedRegistry = OperationRegistry[TestOp, IncrementOp]
    >>> type MorePrivilegedRegistry = OperationRegistry[TestOp, SetIntegerOp]
    >>> type StringRegistry = OperationRegistry[ConcatenateOp, ReplaceSubstringOp, IncrementStringOp]
    """

    _spec: ClassVar[RegistrySpecs]

    def __new__(cls, *_: object, **__: object) -> OperationRegistry[*Ops]:
        raise TypeError(
            f"{cls.__name__} is a registry type and cannot be instantiated. "
            "Use it directly via OperationRegistry[Op1, Op2, ...]."
        )

    def __class_getitem__(cls, args: object) -> type[AnyRegistry]:
        # normalize
        params: tuple[object, ...] = args if isinstance(args, tuple) else (args,)
        try:
            spec = RegistrySpecs(ops=cast(tuple[type[OperationSchema], ...], params))
        except ValidationError as exc:
            raise InvalidOperationRegistry(str(exc)) from exc

        # subtype
        name = cls._registry_type_name(spec.ordered_ops)
        namespace = {"_spec": spec}
        registry_type = type(name, (cls,), namespace)
        return registry_type

    @staticmethod
    def _registry_type_name(ops: tuple[type[OperationSchema], ...]) -> str:
        if ops == _STANDARD_REGISTRY_SPECS.ordered_ops:
            return "StandardRegistry"
        op_names = "_".join(op.__name__ for op in ops)
        return f"OperationRegistry_{op_names}"

    @classmethod
    def model_for(cls, instruction: str) -> type[OperationSchema]:
        model = cls._spec.model_map.get(instruction)
        if model is None:
            raise OperationNotRecognized(
                f"Patch operation '{instruction}' is not allowed in this registry"
            )
        return model

    @classmethod
    def ops(cls) -> tuple[type[OperationSchema], ...]:
        return cls._spec.ordered_ops

    @classmethod
    def union(cls) -> TypeAliasType:
        return cls._spec.union

    @classmethod
    def parse_python_op(
        cls, obj: Mapping[str, JSONValue] | OperationSchema
    ) -> OperationSchema:
        if isinstance(obj, OperationSchema):
            if type(obj) not in cls.ops():
                raise OperationNotRecognized(
                    f"Operation {type(obj).__name__} is not allowed in this registry"
                )
            return obj
        return cls._spec.op_adapter.validate_python(
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
                if type(item) not in cls.ops():
                    raise OperationNotRecognized(
                        f"Operation {type(item).__name__} is not allowed in this registry"
                    )
                ops.append(item)
            else:
                ops.append(
                    cls._spec.op_adapter.validate_python(
                        item,
                        strict=True,
                        by_alias=True,
                        by_name=False,
                    )
                )
        return ops

    @classmethod
    def parse_json_op(cls, text: str | bytes | bytearray) -> OperationSchema:
        return cls._spec.op_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    @classmethod
    def parse_json_patch(cls, text: str | bytes | bytearray) -> list[OperationSchema]:
        return cls._spec.patch_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )


StandardRegistry = OperationRegistry[AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp]
