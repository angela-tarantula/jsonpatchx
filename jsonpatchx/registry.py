from __future__ import annotations

import types
from abc import ABCMeta
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from functools import cached_property
from inspect import isabstract
from typing import (
    Annotated,
    Any,
    Generic,
    TypeAliasType,
    TypeVar,
    Union,
    cast,
    get_args,
    get_origin,
    overload,
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
from typing_extensions import TypeForm

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
from jsonpatchx.types import JSONValue, _type_adapter_for

TModel = TypeVar("TModel", bound=OperationSchema, covariant=True)
type AnyRegistry = OperationRegistry[OperationSchema]


class _RegistrySpecs(BaseModel):
    """Internal canonical form of an operation registry.

    Normalizes a registry's operation models into a validated, deterministic
    representation used for caching, equality, and discriminated-union
    construction.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    ops: frozenset[type[OperationSchema]] = Field(min_length=1)

    @field_validator("ops", mode="before")
    @classmethod
    def _normalize_ops(cls, value: object) -> object:
        """Normalize ``OperationRegistry[...]`` input into a frozenset of candidates.

        Accepts a single class or a union expression (``OpA | OpB | ...``).
        Rejects generic iterables so comma/sequence-style inputs are not accepted.

        Note:
            This validator only normalizes input shape. Pydantic enforces that each
            resulting member is ``type[OperationSchema]``.
        """
        if get_origin(value) in (Union, types.UnionType):
            # NOTE: in Py3.14+, simplify to isinstance(obj, Union) (https://docs.python.org/3.14/library/typing.html#typing.Union)
            return frozenset(get_args(value))
        if isinstance(value, Iterable):
            raise TypeError(
                "OperationRegistry[...] expects a single patch operation class or a union "
                "expression of them; use OperationRegistry[OpA | OpB | ...]"
            )
        return frozenset([value])

    @model_validator(mode="after")
    def _validate_ops(self) -> _RegistrySpecs:
        """Validate registry invariants for ``ops``.

        Ensures the registry contains only concrete operation models and that
        both model names and ``op`` discriminator literals are unique.

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
        """Canonical ordered tuple of operation models for this registry."""
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
        """Mapping of each allowed ``op`` literal to its operation model."""
        return {
            op_literal: model
            for model in self.ordered_ops
            for op_literal in model._op_literals
        }

    @cached_property
    def union(self) -> TypeForm[OperationSchema]:
        """Discriminated union alias for this registry's operation models.

        Used for Pydantic validation and JSON Schema generation with ``op`` as
        the discriminator.
        """
        RegistryPatchOperation = Annotated[
            Union[self.ordered_ops],  # type: ignore[name-defined]
            Field(discriminator="op"),
        ]
        return RegistryPatchOperation

    @cached_property
    def op_adapter(self) -> TypeAdapter[OperationSchema]:
        """TypeAdapter for validating a single registry-bound operation."""
        return _type_adapter_for(self.union)

    @cached_property
    def patch_adapter(self) -> TypeAdapter[list[OperationSchema]]:
        """TypeAdapter for validating a registry-bound patch document."""
        return _type_adapter_for(list[self.union])  # type: ignore[name-defined]

    @cached_property
    def is_RFC6902(self) -> bool:
        """Whether this registry is exactly the built-in RFC 6902 registry."""
        return self.ordered_ops == STANDARD_OPS


STANDARD_OPS = (AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp)
"""Standard RFC 6902 patch operations."""  # in canonical order

_REGISTRY_CACHE: dict[_RegistrySpecs, type[AnyRegistry]] = {}


class _RegistryMeta(ABCMeta):
    """Internal metaclass for ``OperationRegistry``.

    Handles class-level registry composition and guards the distinction between
    the unparameterized factory type and concrete registry subtypes created by
    ``OperationRegistry[...]``.
    """

    _spec: _RegistrySpecs  # Each OperationRegistry subtype has a ClassVar[_RegistrySpecs] defining its operations; the base factory's _spec is undefined
    """Controversial design choice:
    Each parametrized registry type is a separate class with its own ``_RegistrySpecs`` class attribute.
    This means the OperationRegistry class is being overloaded with two distinct responsibilities: when it's unparametrized,
    it's a factory for creating registries, and when it's parametrized, it's a registry with its own specs.

    This overloading requires some guard logic in each method that checks whether _spec is defined or not, as a proxy for
    whether the class is parametrized or not, in order to prevent misuse of the base factory as a registry and vice versa.
    This is admittedly hacky.

    The way out of this pattern would be to avoid relying on parameterized OperationRegistries having their own class attributes.
    Instead, OperationRegistry[...] would be a hollow data container type, and it would be the responsibility of all consumers to
    resolve the registry's specs from that data container whenever they need to do something with it.

    Reasons for the current design that actually have strong rebuttals:
    1. It is preferable to fail fast and reject invalid registry definitions at the point of declaration.
        - Rebuttal: Considering how registries are likely not passed around much before being passed to official consumers,
          it's not a big deal to fail later rather than sooner, and the error messages are going to be just as clear anyway.
    2. It is preferable to cache registries for properties like ``OperationRegistry[OpA | OpB] is OperationRegistry[OpB | OpA]``.
       In other words, key invariants are emergent from the registry's definition rather than relying on consumers to use the
       canonical intepretation of registry definitions.
        - Rebuttal: Consider how ``list[3]`` is valid Python syntax but not a valid type. Just like it's the responsibility of
          type checkers to reject that, it should be the responsibility of registry consumers to reject invalid registry types.
          In essence this debate is about how blind the OperationRegistry definition should be to the idea of "registry-ness".
          The current design encodes the idea of "registry-ness" into the type system and uses that to enforce invariants, while
          the alternative design treats "registry-ness" as the consumer's responsibility to enforce. The latter is more "Pythonic".
    3. Caching registries helps with performance.
       - Rebuttal: Performance is not a concern because registry resolution is neither hot nor expensive (type adapters are
        already cached with ``_type_adapter_for``). Also this library is not aiming to be the fastest possible implementation,
        but rather a first-of-its-kind implementation with a strong focus on correctness, usability, and maintainability.
        Registries are cached for convenience: invariants like ``OperationRegistry[OpA | OpB] is OperationRegistry[OpB | OpA]``
        become an emergent property of the implementation, which is nice to have for debugging but not strictly necessary.

    So, why not just do something like:
    type OperationRegistry[Ops: type[OperationSchema]] = Set[Ops]

    And expand _RegistrySpecs to be a standalone class that can be instantiated from an OperationRegistry type alias, and then
    resolved from the registry type alias whenever needed by official consumers?
    I think that's what I'm going to do...
    """

    def _reject_unparametrized_usage(self) -> None:
        """Guard against methods that require ``_spec`` to be defined."""
        try:
            self._spec.ordered_ops
        except AttributeError as e:
            raise TypeError(f"{self.__name__} is missing patch operations.") from e

    def _reject_parametrized_usage(self) -> None:
        """Guard against methods that require ``_spec`` to be undefined."""
        try:
            self._spec.ordered_ops
        except AttributeError:
            return
        raise TypeError(f"{self.__name__} is already has patch operations.")

    @overload
    def __or__[LModel: OperationSchema, RModel: OperationSchema](  # type: ignore[misc]
        self: type[OperationRegistry[LModel]],
        other: type[OperationRegistry[RModel]],
    ) -> type[OperationRegistry[LModel | RModel]]: ...

    @overload
    def __or__[L, R](self: L, other: R) -> L | R: ...

    @override
    def __or__(self: Any, other: Any) -> Any:
        return Union[self, other]

    __ror__ = __or__


class OperationRegistry(Generic[TModel], metaclass=_RegistryMeta):
    """Type-level registry of allowed patch operation models.

    ``OperationRegistry[...]`` declares which ``OperationSchema`` subclasses are
    valid for a particular patch surface. The registry then drives operation
    parsing, ``op`` dispatch, and schema generation.

    Registries are canonicalized by operation set rather than declaration
    order, so equivalent declarations resolve to the same runtime type.

    Examples:
        Declare a registry statically:

        >>> type PlayerRegistry = OperationRegistry[AddOp | ReplaceOp | IncrementOp]

        Build one dynamically:

        >>> enabled_ops = [AddOp, ReplaceOp, IncrementOp]
        >>> type PlayerRegistry = OperationRegistry.of(*enabled_ops)
    """

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
        cls._reject_parametrized_usage()
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
    def ops(cls) -> tuple[type[OperationSchema], ...]:
        """Operation models allowed by this registry."""
        cls._reject_unparametrized_usage()
        return cls._spec.ordered_ops

    @classmethod
    def union(cls) -> TypeForm[OperationSchema]:
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

        As this method creates a runtime type, type-checkers will complain
        that it's not a valid type, but you can ignore that.

        Args:
            *ops: Concrete ``OperationSchema`` subclasses to include.

        Returns:
            A canonicalized registry subtype for the provided operation set.

        Raises:
            InvalidOperationRegistry: If the operation set is empty or violates
                registry invariants.

        Examples:
            >>> enabled = [AddOp, ReplaceOp, IncrementOp]
            >>> type PlayerRegistry = OperationRegistry.of(*enabled)  # type: ignore[valid-type]
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


def resolve_registry_typeform(
    registry: TypeForm[AnyRegistry] | object,
) -> type[AnyRegistry]:
    """Resolve a registry type expression into a concrete ``OperationRegistry`` class.

    This accepts a concrete registry type, a type alias to one, or a union of
    registry types. Unions are merged by combining the operations from each
    registry into a single canonical registry type.

    Args:
        registry: Registry type expression to resolve.

    Returns:
        A concrete ``OperationRegistry[...]`` subtype.

    Raises:
        TypeError: If ``registry`` is not a supported registry type expression.
    """
    if isinstance(registry, TypeAliasType):
        return resolve_registry_typeform(registry.__value__)

    if get_origin(registry) is Union:
        # Implements the rule that OperationRegistry[A] | OperationRegistry[B] = OperationRegistry[A | B],
        # as defined in the __or__ operator of _RegistryMeta.
        args = get_args(registry)
        merged_ops: frozenset[type[OperationSchema]] = frozenset()
        for arg in args:
            resolved = resolve_registry_typeform(arg)
            merged_ops |= resolved._spec.ops
        return OperationRegistry.of(*merged_ops)

    if isinstance(registry, _RegistryMeta):
        resolved = cast(type[AnyRegistry], registry)
        resolved._reject_unparametrized_usage()
        return resolved

    raise TypeError(
        "Expected an OperationRegistry type, a type alias to one, or a union of them; "
        f"got {registry!r}"
    )
