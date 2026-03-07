from __future__ import annotations

import types
from abc import ABCMeta
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from functools import cached_property
from inspect import isabstract
from typing import (
    Annotated,
    ClassVar,
    Generic,
    TypeAliasType,
    TypeVar,
    Union,
    cast,
    override,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

from jsonpatchx.builtins import (
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

TModel = TypeVar("TModel", bound=OperationSchema, covariant=True)
type AnyRegistry = OperationRegistry[OperationSchema]


class _RegistrySpecs(BaseModel):
    """Internal canonical representation of an operation registry.

    Normalizes a set of concrete ``OperationSchema`` classes into a stable,
    validated form used for registry caching, equality, and Pydantic union
    construction.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    ops: frozenset[type[OperationSchema]] = Field(min_length=1)

    @field_validator("ops", mode="before")
    @classmethod
    def _normalize_ops(cls, value: object) -> object:
        if isinstance(value, types.UnionType):
            return frozenset(value.__args__)
        if isinstance(value, Iterable):
            raise TypeError(
                "OperationRegistry[...] expects a single patch operation class or a union "
                "expression of them; use OperationRegistry[OpA | OpB | ...]"
            )
        return frozenset([value])

    @model_validator(mode="after")
    def _validate_ops(self) -> _RegistrySpecs:
        """Validate registry invariants for ``ops``.

        Ensures the registry is non-empty, contains only concrete operation
        models, and has no duplicate model names or ``op`` discriminator values.

        Raises:
            InvalidOperationRegistry: If the registry definition is unusable.
        """

        non_concrete_models = sorted(
            model.__name__ for model in self.ops if isabstract(model)
        )
        if non_concrete_models:
            raise InvalidOperationRegistry(
                "Expected concrete OperationSchema classes, got abstract models: "
                f"{non_concrete_models!r}"
            )

        def duplicates(values: Iterable[str]) -> list[str]:
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
        """Canonical tuple of operation models for this registry."""
        return tuple(sorted(self.ops, key=lambda op: op._op_literals[0]))

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _RegistrySpecs):
            return NotImplemented
        return self.ordered_ops == other.ordered_ops

    @override
    def __hash__(self) -> int:
        return hash(self.ordered_ops)

    @cached_property
    def model_map(self) -> Mapping[str, type[OperationSchema]]:
        """Mapping from each allowed ``op`` literal to its operation model."""
        return {
            op_literal: model
            for model in self.ordered_ops
            for op_literal in model._op_literals
        }

    @cached_property
    def union(self) -> TypeAliasType:
        """Discriminated union alias for this registry's operation models.

        Used for Pydantic validation and JSON Schema generation with ``op`` as
        the discriminator.
        """
        type RegistryPatchOperation = Annotated[
            Union[self.ordered_ops],  # type: ignore[name-defined]
            Field(discriminator="op"),
        ]
        return RegistryPatchOperation

    @cached_property
    def op_adapter(self) -> TypeAdapter[OperationSchema]:
        """TypeAdapter for validating a single registry-bound operation."""
        return TypeAdapter(self.union)

    @cached_property
    def patch_adapter(self) -> TypeAdapter[list[OperationSchema]]:
        """TypeAdapter for validating a full registry-bound patch document."""
        return TypeAdapter(list[self.union])  # type: ignore[name-defined]

    @cached_property
    def is_RFC6902(self) -> bool:
        """Whether this registry is exactly the built-in RFC 6902 registry."""
        return self.ordered_ops == STANDARD_OPS


_STANDARD_REGISTRY_SPECS = _RegistrySpecs(
    ops=AddOp | CopyOp | MoveOp | RemoveOp | ReplaceOp | TestOp
)

STANDARD_OPS = _STANDARD_REGISTRY_SPECS.ordered_ops
"""Standard RFC 6902 patch operations."""

_REGISTRY_CACHE: dict[_RegistrySpecs, type[AnyRegistry]] = {}


class _RegistryMeta(ABCMeta):
    @override
    def __or__(cls, other: object) -> type[AnyRegistry]:
        if not isinstance(other, _RegistryMeta):
            return NotImplemented

        left = cast(type[AnyRegistry], cls)
        right = cast(type[AnyRegistry], other)

        left._reject_unparametrized_usage()
        right._reject_unparametrized_usage()

        merged_ops = left._spec.ops | right._spec.ops
        return OperationRegistry.of(*merged_ops)

    @override
    def __ror__(cls, other: object) -> type[AnyRegistry]:
        if not isinstance(other, _RegistryMeta):
            return NotImplemented

        left = cast(type[AnyRegistry], other)
        right = cast(type[AnyRegistry], cls)

        left._reject_unparametrized_usage()
        right._reject_unparametrized_usage()

        merged_ops = left._spec.ops | right._spec.ops
        return OperationRegistry.of(*merged_ops)


class OperationRegistry(Generic[TModel], metaclass=_RegistryMeta):
    """Type-level registry of allowed patch operation models.

    ``OperationRegistry[...]`` declares which ``OperationSchema`` subclasses are
    valid for a particular patch surface. The registry then drives operation
    parsing, ``op`` dispatch, and schema generation.

    Registries are canonicalized by operation set rather than declaration
    order, so equivalent declarations resolve to the same runtime type.

    Examples:
        Declare a registry statically:

        >>> PlayerRegistry = OperationRegistry[AddOp | ReplaceOp | IncrementOp]

        Build one dynamically:

        >>> enabled_ops = [AddOp, ReplaceOp, IncrementOp]
        >>> PlayerRegistry = OperationRegistry.of(*enabled_ops)
    """

    _spec: ClassVar[_RegistrySpecs]

    def __new__(cls, *_: object, **__: object) -> OperationRegistry[TModel]:
        raise TypeError(
            f"{cls.__name__} is a registry type and cannot be instantiated."
        )

    def __class_getitem__(cls, args: object) -> type[AnyRegistry]:
        """Create a registry type from one or more operation models.

        This powers ``OperationRegistry[...]`` syntax and returns a canonicalized
        registry subtype for the provided operation set.

        Raises:
            InvalidOperationRegistry: If the supplied operation set is invalid.
        """
        try:
            spec = _RegistrySpecs(ops=args)
        except (ValidationError, TypeError) as exc:
            raise InvalidOperationRegistry(str(exc)) from exc

        cached = _REGISTRY_CACHE.get(spec)
        if cached is not None:
            return cached

        name = cls._registry_type_name(spec)
        namespace = {"_spec": spec}
        registry_type = type(name, (cls,), namespace)

        _REGISTRY_CACHE[spec] = registry_type
        return registry_type

    @staticmethod
    def _registry_type_name(spec: _RegistrySpecs) -> str:
        """Return the deterministic runtime name for a registry subtype."""
        if spec.is_RFC6902:
            return "StandardRegistry"
        op_names = "_".join(op.__name__ for op in spec.ordered_ops)
        return f"OperationRegistry_{op_names}"

    @classmethod
    def _reject_unparametrized_usage(cls) -> None:
        """Guard against methods that require the ``_spec`` to be defined."""
        if not hasattr(cls, "_spec"):
            raise TypeError(f"{cls.__name__} is missing patch operations.")

    @classmethod
    def ops(cls) -> tuple[type[OperationSchema], ...]:
        """Operation models allowed by this registry."""
        cls._reject_unparametrized_usage()
        return cls._spec.ordered_ops

    @classmethod
    def union(cls) -> TypeAliasType:
        """Discriminated union type for this registry's operations.

        Useful for advanced validation and schema-generation workflows.
        """
        cls._reject_unparametrized_usage()
        return cls._spec.union

    @classmethod
    def model_for(cls, instruction: str) -> type[OperationSchema]:
        """Resolve an ``op`` value to its registered operation model.

        Args:
            instruction: Operation name from a patch payload.

        Returns:
            The concrete ``OperationSchema`` class registered for that name.

        Raises:
            OperationNotRecognized: If the operation is not allowed by this
                registry.
        """
        cls._reject_unparametrized_usage()
        model = cls._spec.model_map.get(instruction)
        if model is None:
            raise OperationNotRecognized(
                f"Patch operation '{instruction}' is not allowed in this registry"
            )
        return model

    @classmethod
    def parse_python_op(
        cls, obj: Mapping[str, JSONValue] | OperationSchema
    ) -> OperationSchema:
        """Validate one Python operation payload against this registry.

        Accepts either a mapping payload or an existing operation instance. Model
        instances are accepted only if their concrete type is allowed by this
        registry.

        Args:
            obj: Operation payload as a mapping, or a concrete operation instance.

        Returns:
            A validated concrete operation model.

        Raises:
            OperationNotRecognized: If an operation instance is not allowed by
                this registry.
            ValidationError: If a mapping payload fails validation.
        """
        cls._reject_unparametrized_usage()
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
        """Validate a Python patch document against this registry.

        Each item may be either a mapping payload or an existing operation
        instance. Model instances are accepted only if their concrete type is
        allowed by this registry.

        Args:
            python: Patch document as Python mappings and/or operation instances.

        Returns:
            A list of validated concrete operation models.

        Raises:
            OperationNotRecognized: If an operation instance is not allowed by
                this registry.
            ValidationError: If any payload fails validation.
        """
        cls._reject_unparametrized_usage()
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
        """Validate one JSON-encoded operation against this registry.

        Args:
            text: JSON representation of a single patch operation.

        Returns:
            A validated concrete operation model.

        Raises:
            ValidationError: If the JSON is malformed or the payload does not
                match an allowed operation model.
        """
        cls._reject_unparametrized_usage()
        return cls._spec.op_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    @classmethod
    def parse_json_patch(cls, text: str | bytes | bytearray) -> list[OperationSchema]:
        """Validate a JSON-encoded patch document against this registry.

        Args:
            text: JSON representation of a patch array.

        Returns:
            A list of validated concrete operation models.

        Raises:
            ValidationError: If the JSON is malformed or any operation fails
                validation.
        """
        cls._reject_unparametrized_usage()
        return cls._spec.patch_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    @classmethod
    def of(cls, *ops: type[OperationSchema]) -> type[AnyRegistry]:
        """Create a registry type from operation models at runtime.

        Use this when the allowed operation set is assembled dynamically rather
        than written directly as ``OperationRegistry[...]``.

        Args:
            *ops: Concrete ``OperationSchema`` subclasses to include.

        Returns:
            A canonicalized registry subtype for the provided operation set.

        Raises:
            InvalidOperationRegistry: If the operation set is empty or violates
                registry invariants.

        Examples:
            >>> enabled = [AddOp, ReplaceOp, IncrementOp]
            >>> PlayerRegistry = OperationRegistry.of(*enabled)
        """
        if not ops:
            raise InvalidOperationRegistry(
                "OperationRegistry requires at least one operation model"
            )
        registry_arg: type[OperationSchema] | types.UnionType = ops[0]
        for op in ops[1:]:
            registry_arg = registry_arg | op
        return cls.__class_getitem__(registry_arg)


StandardRegistry = OperationRegistry[
    AddOp | CopyOp | MoveOp | RemoveOp | ReplaceOp | TestOp
]
"""Standard RFC 6902 registry containing the built-in patch operations."""
