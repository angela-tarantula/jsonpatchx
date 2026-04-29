from __future__ import annotations

import types
from collections import Counter
from collections.abc import Generator, Iterable, Mapping, Sequence
from functools import cached_property
from inspect import isabstract
from typing import (
    Annotated,
    Any,
    TypeAliasType,
    Union,
    cast,
    get_args,
    get_origin,
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
from typing_extensions import TypeForm

from jsonpatchx.builtins import (
    AddOp,
    CopyOp,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
from jsonpatchx.exceptions import InvalidOperationRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue


def _iter_union_members[T](value: TypeForm[T]) -> Generator[type[T]]:
    """Yield leaf members from an operation type expression.

    Performs structural unpacking only: unwraps type aliases, flattens
    unions, and strips `Annotated` wrappers.

    Arguments:
        value: A type expression to unpack, such as a union of operation
            models or a type alias of those forms.

    Yields:
        Leaf member types from the expression, without validation.

    Raises:
        InvalidOperationRegistry: If the expression contains an
            unsupported generic origin.

    Notes:
        Does not validate member types or resolve forward references.
        Pydantic enforces those constraints in `_RegistrySpec.ops`.
    """
    if isinstance(value, TypeAliasType):
        yield from _iter_union_members(value.__value__)
    elif get_origin(value) in (Union, types.UnionType):
        # Update for Py3.14+: https://docs.python.org/3/library/typing.html#:~:text=For%20compatibility%20with%20earlier%20versions%20of%20Python%2C%20use%20get_origin(obj)%20is%20typing.Union%20or%20get_origin(obj)%20is%20types.UnionType
        for arg in get_args(value):
            yield from _iter_union_members(arg)
    elif get_origin(value) is Annotated:
        yield from _iter_union_members(get_args(value)[0])
    elif get_origin(value) is None:
        yield cast(type[T], value)
    else:
        raise InvalidOperationRegistry(
            f"Unsupported type expression {get_origin(value)!r} in registry declaration: {value!r}"
        )


class _RegistrySpec(BaseModel):
    """Internal canonical form of an operation registry.

    Normalizes a registry's operation models into a validated, deterministic
    representation used for caching, equality, and discriminated-union
    construction.
    """

    model_config = ConfigDict(frozen=True, validate_return=True)

    ops: frozenset[type[OperationSchema]] = Field(min_length=1)

    @classmethod
    def from_typeform(cls, typeform: TypeForm[OperationSchema] | Any) -> _RegistrySpec:
        """Build a validated spec from a type-form operation declaration.

        Arguments:
            typeform: A single operation model or union of models, including
                nested type aliases of those forms.

        Returns:
            A validated `_RegistrySpec` for the operation declaration.

        Raises:
            InvalidOperationRegistry: If the declaration cannot define a valid
                operation registry.
        """
        try:
            return cls(ops=frozenset(_iter_union_members(typeform)))
        except ValidationError as exc:
            raise InvalidOperationRegistry(
                "Invalid registry declaration: registry must be a union of concrete OperationSchemas "
                f"(OpA | OpB | ...). Details: {exc}"
            ) from exc

    @model_validator(mode="after")
    def _validate_ops(self) -> _RegistrySpec:
        """Validate registry invariants for `ops`.

        Ensures the registry contains only concrete operation models with
        unique class names and `op` discriminator literals.

        Returns:
            This registry spec, unchanged, if all invariants hold.

        Raises:
            InvalidOperationRegistry: If the registry contains abstract models,
                duplicate class names, or duplicate `op` literals.

        Notes:
            Implemented as a model validator rather than a field validator so
            that it remains correct if additional fields are added to the spec
            in the future.
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
        return tuple(sorted(self.ops, key=lambda op: min(op._op_literals)))

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _RegistrySpec):
            return NotImplemented
        return self.ops == other.ops

    @override
    def __hash__(self) -> int:
        return hash((self.__class__, self.ops))

    @cached_property
    def model_map(self) -> Mapping[str, type[OperationSchema]]:
        """Mapping of each allowed `op` literal to its operation model."""
        return {
            op_literal: model
            for model in self.ordered_ops
            for op_literal in model._op_literals
        }

    @cached_property
    def union_type(self) -> TypeForm[OperationSchema]:
        """Discriminated union alias for this registry's operation models.

        Used for Pydantic validation and JSON Schema generation with `op` as
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
        return TypeAdapter(self.union_type)

    @cached_property
    def patch_adapter(self) -> TypeAdapter[list[OperationSchema]]:
        """TypeAdapter for validating a registry-bound patch document."""
        return TypeAdapter(list[self.union_type])  # type: ignore[name-defined]

    def model_for(self, instruction: str) -> type[OperationSchema]:
        """Resolve an `op` literal to its registered operation model.

        Arguments:
            instruction: The `op` literal string to look up.

        Returns:
            The registered `OperationSchema` subclass for `instruction`.

        Raises:
            KeyError: If `instruction` is not registered.
        """
        model = self.model_map.get(instruction)
        if model is None:
            raise KeyError(
                f"Patch operation '{instruction}' is not allowed in this registry"
            )
        return model

    def parse_python_op(
        self, obj: Mapping[str, JSONValue] | OperationSchema
    ) -> OperationSchema:
        """Validate one Python operation payload against this registry.

        Arguments:
            obj: A mapping of operation fields, or an already-validated
                `OperationSchema` instance.

        Returns:
            A validated `OperationSchema` instance.

        Raises:
            ValidationError: If `obj` fails Pydantic validation.
        """
        return self.op_adapter.validate_python(
            obj,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    def parse_python_patch(
        self, python: Sequence[OperationSchema | Mapping[str, JSONValue]]
    ) -> list[OperationSchema]:
        """Validate a Python patch document against this registry.

        Arguments:
            python: A sequence of operation mappings or `OperationSchema`
                instances.

        Returns:
            A list of validated `OperationSchema` instances.

        Raises:
            ValidationError: If any item fails Pydantic validation.
        """
        return self.patch_adapter.validate_python(
            list(python),
            strict=True,
            by_alias=True,
            by_name=False,
        )

    def parse_json_op(self, text: str | bytes | bytearray) -> OperationSchema:
        """Validate one JSON-encoded operation against this registry.

        Arguments:
            text: A JSON string, bytes, or bytearray encoding a single
                operation object.

        Returns:
            A validated `OperationSchema` instance.

        Raises:
            ValidationError: If `text` fails Pydantic validation.
        """
        return self.op_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    def parse_json_patch(self, text: str | bytes | bytearray) -> list[OperationSchema]:
        """Validate a JSON-encoded patch document against this registry.

        Arguments:
            text: A JSON string, bytes, or bytearray encoding a patch array.

        Returns:
            A list of validated `OperationSchema` instances.

        Raises:
            ValidationError: If `text` fails Pydantic validation.
        """
        return self.patch_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
        )

    @cached_property
    def is_rfc6902(self) -> bool:
        """Whether this registry is exactly the built-in RFC 6902 registry."""
        return self.ops == _STANDARD_REGISTRY_SPEC.ops


type StandardRegistry = AddOp | CopyOp | MoveOp | RemoveOp | ReplaceOp | TestOp
"""Standard RFC 6902 registry declaration typeform."""

_STANDARD_REGISTRY_SPEC = _RegistrySpec.from_typeform(StandardRegistry)
"""Resolved RFC 6902 registry spec."""
