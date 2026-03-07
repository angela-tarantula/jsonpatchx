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
    override,
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
    """
    Canonicalized metadata and parsing artifacts for a registry of operation models.

    ``RegistrySpecs`` normalizes an unordered set of concrete ``OperationSchema``
    subclasses into a deterministic representation that can be used for caching,
    discriminated-union construction, and validation. Two registries containing
    the same operation models are considered equivalent regardless of declaration
    order.

    Attributes:
        ops:
            The unique set of operation models included in this specification.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    ops: frozenset[type[OperationSchema]]

    @model_validator(mode="after")
    def _validate_ops(self) -> RegistrySpecs:
        """
        Validate that the registry specification defines a usable operation set.

        Validation enforces the following invariants:

        - at least one operation model must be present
        - all models must be concrete subclasses of ``OperationSchema``
        - model class names must be unique
        - ``op`` discriminator literals must be unique across all models

        Returns:
            The validated registry specification.

        Raises:
            InvalidOperationRegistry:
                If the operation set is empty, contains abstract models,
                duplicates class names, or reuses one or more ``op`` literals.
        """

        if not self.ops:
            raise InvalidOperationRegistry(
                "OperationRegistry requires at least one operation model"
            )

        non_concrete_models = sorted(
            model.__name__ for model in self.ops if isabstract(model)
        )
        if non_concrete_models:
            raise InvalidOperationRegistry(
                "Expected concrete OperationSchema classes, got abstract models: "
                f"{non_concrete_models!r}"
            )

        def duplicates(values: Iterable[str]) -> list[str]:
            """
            Return duplicate string values in sorted order.

            Sorting keeps error output deterministic, which improves test stability
            and makes diagnostics easier to compare across runs.

            Args:
                values:
                    The string values to inspect.

            Returns:
                A sorted list of duplicated values.
            """
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
        """
        Return the operation models in canonical order.

        The order is derived from each model's first declared ``op`` literal and is
        used to keep generated unions, adapter behavior, and cache identity stable
        across equivalent registry declarations.

        Returns:
            A deterministic tuple of operation model classes.
        """
        return tuple(sorted(self.ops, key=lambda op: op._op_literals[0]))

    @override
    def __eq__(self, other: object) -> bool:
        """
        Compare registry specifications by canonical operation ordering.

        Declaration order is intentionally ignored so that equivalent registries
        compare equal even when constructed from differently ordered inputs.

        Args:
            other:
                The object to compare against.

        Returns:
            ``True`` if both specifications contain the same canonicalized
            operation set; otherwise ``False``.
        """
        if not isinstance(other, RegistrySpecs):
            return NotImplemented
        return self.ordered_ops == other.ordered_ops

    @override
    def __hash__(self) -> int:
        """
        Hash the registry specification by canonical operation ordering.

        Returns:
            A hash value derived from ``ordered_ops``.
        """
        return hash(self.ordered_ops)

    @cached_property
    def model_map(self) -> Mapping[str, type[OperationSchema]]:
        """
        Build a lookup from each ``op`` literal to its owning model class.

        Returns:
            A mapping from operation discriminator string to the concrete
            ``OperationSchema`` subclass that handles it.
        """
        return {
            op_literal: model
            for model in self.ordered_ops
            for op_literal in model._op_literals
        }

    @cached_property
    def union(self) -> TypeAliasType:
        """
        Construct the discriminated union type for this registry.

        The resulting alias is suitable for use with Pydantic validation and
        JSON Schema generation. Dispatch is performed using the ``op`` field.

        Returns:
            A ``TypeAliasType`` representing the registry's discriminated union
            of operation models.
        """
        type RegistryPatchOperation = Annotated[
            Union[self.ordered_ops],  # type: ignore[name-defined]
            Field(discriminator="op"),
        ]
        return RegistryPatchOperation

    @cached_property
    def op_adapter(self) -> TypeAdapter[OperationSchema]:
        """
        Create the Pydantic adapter for validating a single operation payload.

        Returns:
            A ``TypeAdapter`` that validates one registry-bound patch operation.
        """
        return TypeAdapter(self.union)

    @cached_property
    def patch_adapter(self) -> TypeAdapter[list[OperationSchema]]:
        """
        Create the Pydantic adapter for validating a full patch document.

        Returns:
            A ``TypeAdapter`` that validates a list of registry-bound patch
            operations.
        """
        return TypeAdapter(list[self.union])  # type: ignore[name-defined]

    @cached_property
    def is_RFC6902(self) -> bool:
        """
        Indicate whether this registry matches the standard RFC 6902 operation set.

        Returns:
            ``True`` if the registry contains exactly the built-in RFC 6902
            operations in canonical order; otherwise ``False``.
        """
        return self.ordered_ops == STANDARD_OPS


_STANDARD_REGISTRY_SPECS = RegistrySpecs(
    ops=frozenset([AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp])
)
STANDARD_OPS = _STANDARD_REGISTRY_SPECS.ordered_ops

_REGISTRY_CACHE: dict[RegistrySpecs, type[AnyRegistry]] = {}


class OperationRegistry(Generic[*Ops]):
    """
    Declarative registry type for allowed JSON Patch operation models.

    ``OperationRegistry[...]`` defines a registry as a type-level contract rather
    than an instance. A registry determines which operation models are valid for
    parsing and schema generation, and it can be used anywhere a registry type is
    needed, such as ``JsonPatchFor[Target, Registry]``.

    Registries are canonicalized and cached. Equivalent declarations resolve to
    the same runtime class, regardless of operation declaration order.

    Examples:
        >>> type LeastPrivilegedRegistry = OperationRegistry[TestOp, IncrementOp]
        >>> type MorePrivilegedRegistry = OperationRegistry[TestOp, SetIntegerOp]
        >>> type StringRegistry = OperationRegistry[
        ...     ConcatenateOp,
        ...     ReplaceSubstringOp,
        ...     IncrementStringOp,
        ... ]
    """

    _spec: ClassVar[RegistrySpecs]

    def __new__(cls, *_: object, **__: object) -> OperationRegistry[*Ops]:
        """
        Prevent instantiation of registry types.

        ``OperationRegistry`` classes are declarative type artifacts, not runtime
        service objects. They are intended to be referenced directly rather than
        instantiated.

        Raises:
            TypeError:
                Always raised to indicate that registry types cannot be
                instantiated.
        """
        raise TypeError(
            f"{cls.__name__} is a registry type and cannot be instantiated. "
            "Use it directly via OperationRegistry[Op1, Op2, ...]."
        )

    def __class_getitem__(cls, args: object) -> type[AnyRegistry]:
        """
        Create or retrieve a registry subtype for the given operation models.

        This method powers the ``OperationRegistry[...]`` syntax. The provided
        operation models are normalized into a canonical ``RegistrySpecs`` object,
        validated, and then resolved through a cache so that equivalent operation
        sets share the same registry class.

        Args:
            args:
                Either a single operation model or a tuple of operation models.

        Returns:
            A dynamically generated registry subtype representing the provided
            operation set.

        Raises:
            InvalidOperationRegistry:
                If the provided operation set does not satisfy the registry
                invariants.
        """
        params: tuple[object, ...] = args if isinstance(args, tuple) else (args,)

        try:
            spec = RegistrySpecs(ops=params)
        except ValidationError as exc:
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
    def _registry_type_name(spec: RegistrySpecs) -> str:
        """
        Derive a stable runtime name for a registry subtype.

        The standard RFC 6902 registry receives the special name
        ``"StandardRegistry"``. Other registries are named from their canonical
        ordered operation model names.

        Args:
            spec:
                The registry specification to name.

        Returns:
            The runtime class name for the generated registry subtype.
        """
        if spec.is_RFC6902:
            return "StandardRegistry"
        op_names = "_".join(op.__name__ for op in spec.ordered_ops)
        return f"OperationRegistry_{op_names}"

    @classmethod
    def ops(cls) -> tuple[type[OperationSchema], ...]:
        """
        Return the operation models allowed by this registry.

        Returns:
            A tuple of concrete ``OperationSchema`` subclasses in canonical order.
        """
        return cls._spec.ordered_ops

    @classmethod
    def union(cls) -> TypeAliasType:
        """
        Return the discriminated union type for this registry.

        Returns:
            A ``TypeAliasType`` suitable for validation and schema generation of
            registry-bound operations.
        """
        return cls._spec.union

    @classmethod
    def model_for(cls, instruction: str) -> type[OperationSchema]:
        """
        Resolve an ``op`` discriminator value to its operation model.

        Args:
            instruction:
                The patch operation name from the payload's ``op`` field.

        Returns:
            The concrete ``OperationSchema`` subclass registered for that
            instruction.

        Raises:
            OperationNotRecognized:
                If the instruction is not allowed by this registry.
        """
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
        """
        Validate a single Python operation payload against this registry.

        Existing ``OperationSchema`` instances are accepted only if their concrete
        type is allowed by the registry. Mapping payloads are validated through the
        registry's discriminated union adapter.

        Args:
            obj:
                Either an operation model instance or a Python mapping
                representing an operation payload.

        Returns:
            A validated concrete operation model.

        Raises:
            OperationNotRecognized:
                If an operation instance is provided whose type is not allowed by
                this registry.
            ValidationError:
                If a mapping payload fails Pydantic validation.
        """
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
        """
        Validate a Python patch document against this registry.

        Each item may be either an already-instantiated operation model or a
        mapping payload. Existing model instances are checked for membership in the
        registry; mappings are validated item-by-item using the registry's
        operation adapter.

        Args:
            python:
                The patch document as a sequence of operation instances and/or
                mapping payloads.

        Returns:
            A list of validated concrete operation models.

        Raises:
            OperationNotRecognized:
                If an operation instance is present whose type is not allowed by
                this registry.
            ValidationError:
                If any mapping payload fails validation.
        """
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
        """
        Validate a single JSON-encoded operation payload against this registry.

        Args:
            text:
                The JSON text or bytes representing one patch operation.

        Returns:
            A validated concrete operation model.

        Raises:
            ValidationError:
                If the JSON payload is malformed or does not conform to one of the
                registry's allowed operation models.
        """
        return cls._spec.op_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    @classmethod
    def parse_json_patch(cls, text: str | bytes | bytearray) -> list[OperationSchema]:
        """
        Validate a JSON-encoded patch document against this registry.

        Args:
            text:
                The JSON text or bytes representing a full patch array.

        Returns:
            A list of validated concrete operation models.

        Raises:
            ValidationError:
                If the JSON payload is malformed or any operation fails
                validation.
        """
        return cls._spec.patch_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    @classmethod
    def of(cls, *ops: type[OperationSchema]) -> type[AnyRegistry]:
        """
        Create a registry dynamically from a runtime sequence of operation models.

        This method is the runtime counterpart to the ``OperationRegistry[...]``
        type syntax. It is intended for cases where the operation set is assembled
        programmatically, such as from configuration, plugins, or feature flags,
        and therefore cannot be written as static type parameters.

        The returned object is a registry type, not an instance. Registry types are
        canonicalized and cached, so calling ``OperationRegistry.of(...)`` with the
        same effective operation set yields the same class as the equivalent
        ``OperationRegistry[...]`` declaration.

        Args:
            *ops:
                Concrete subclasses of ``OperationSchema`` to include in the
                registry.

        Returns:
            A dynamically generated registry subtype representing the provided
            operation set.

        Raises:
            InvalidOperationRegistry:
                If the operation set is empty, contains abstract models, includes
                duplicate class names, or reuses one or more ``op`` discriminator
                literals.

        Examples:
            Static declaration:

            >>> PlayerRegistry = OperationRegistry[AddOp, ReplaceOp, IncrementOp]

            Dynamic construction:

            >>> ops = [AddOp, ReplaceOp, IncrementOp]
            >>> PlayerRegistry = OperationRegistry.of(*ops)

            Both forms produce equivalent registry types.
        """
        return cls.__class_getitem__(ops)


StandardRegistry = OperationRegistry[AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp]
"""The standard RFC 6902 registry containing the built-in patch operations."""
