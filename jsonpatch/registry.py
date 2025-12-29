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
    Registry for JSON Patch operation types.

    An :class:`OperationRegistry` defines the *operation vocabulary* for your application:

    - which operation schemas are allowed (standard RFC 6902 ops and/or custom ops),
    - how to parse/validate incoming patch documents into concrete :class:`~jsonpatch.schema.OperationSchema` instances,
    - which RFC 6901 pointer backend to use when validating :class:`~jsonpatch.types.JSONPointer[...]` fields.

    This type is a key building block for two common workflows:

    1) **Programmatic patch parsing**
       (validate Python dicts / JSON strings into typed operations)

    2) **Framework integration**
       (FastAPI/OpenAPI request bodies via dynamically generated RootModels)

    ### What the registry provides

    - **Dispatch:** maps each allowed ``op`` identifier to the corresponding OperationSchema subclass.
    - **Validation:** builds a Pydantic discriminated union on the ``op`` field.
    - **Pointer semantics:** injects registry-scoped validation ``context`` so JSONPointer fields
      are instantiated with the registry’s configured pointer backend.

    ### Immutability / safety

    Registries are effectively immutable after construction: they cache the union and adapters
    used for parsing. Treat them as long-lived singletons (module-level constants) rather than
    per-request objects.

    ### Usage

    Standard RFC 6902 registry::

        registry = OperationRegistry.standard()
        op = registry.parse_python_op({"op": "remove", "path": "/foo"})

    Standard + custom ops, optionally with a custom pointer backend::

        registry = OperationRegistry.with_standard(IncrementOp, pointer_cls=MyPointer)
        ops = registry.parse_json_patch(b'[{"op": "increment", "path": "/count", "value": 1}]')

    Notes:
    - The registry does **not** apply patches; it only parses/validates operations.
      Patch application is handled by the patch engine (e.g., ``_apply_ops`` / ``JsonPatch.apply``).
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
        """
        Create a registry from a set of OperationSchema subclasses.

        Args:
            op_schemas:
                One or more :class:`~jsonpatch.schema.OperationSchema` subclasses.
                Each schema must declare ``op: Literal[...]``. The set of op identifiers across
                all schemas must be disjoint.

            pointer_cls:
                The RFC 6901 pointer backend class to use when validating
                :class:`~jsonpatch.types.JSONPointer[...]` fields within these operations.

                This does *not* change the runtime patch semantics directly; it changes how pointer
                strings are parsed/validated and how pointer tokens are interpreted during pointer
                operations.

        Raises:
            InvalidOperationRegistry:
                If no schemas are provided, a schema is abstract/not a class, or op identifiers overlap.

            InvalidJSONPointer:
                If ``pointer_cls("")`` cannot construct a valid root pointer or does not satisfy the
                :class:`~jsonpatch.types.PointerBackend` protocol.

        Notes:
            Registries cache Pydantic TypeAdapters internally. Construct registries once (module scope)
            rather than per request.
        """
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
        """
        Internal: validate that registry inputs are usable for discriminated-union dispatch.

        Requirements:
        - at least one schema
        - each entry is a concrete (non-abstract) class
        - each entry subclasses OperationSchema
        """
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
        """
        Internal: build an ``op`` identifier -> schema type mapping.

        Ensures that all declared ``op: Literal[...]`` identifiers across schemas are disjoint,
        since Pydantic discriminated unions require an unambiguous discriminator value.
        """
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
        Internal: construct the discriminated union type and the cached Pydantic TypeAdapters.

        - ``union_type`` is a runtime-generated ``Annotated[Union[...], Field(discriminator="op")]``.
        - ``op_adapter`` validates a single operation.
        - ``patch_adapter`` validates a list of operations (a JSON Patch document).
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
        """
        Mapping of operation identifier -> OperationSchema type.

        This is primarily useful for tooling and introspection (e.g., building docs,
        debugging registry contents). Most users will not need this directly.
        """
        return self._model_map

    @property
    def ops(self) -> Set[type[OperationSchema]]:
        """
        Set of OperationSchema types registered in this registry.

        Note: if an OperationSchema declares multiple ``op`` identifiers (aliases), it will still
        appear only once in this set.
        """
        return frozenset(self._model_map.values())

    @property
    def union(self) -> TypeAliasType:
        """
        Runtime-generated discriminated union of all registered operation schemas.

        This is primarily intended for framework integration (e.g., as the element type inside a
        Pydantic RootModel request body). Treat it as an implementation detail unless you are
        building custom Pydantic models around the registry.
        """
        return self._union_type

    @property
    def _ctx(self) -> dict[Literal["jsonpatch:pointer_backend"], type[PointerBackend]]:
        """
        Internal: Pydantic validation context injected during parsing.

        This context allows :class:`~jsonpatch.types.JSONPointer[...]` fields to instantiate with the
        registry’s configured pointer backend.
        """
        return {_POINTER_BACKEND_CTX_KEY: self._pointer_cls}

    def parse_python_op(
        self, obj: Mapping[str, JSONValue] | OperationSchema
    ) -> OperationSchema:
        """
        Parse and validate a single operation from a Python object.

        Accepts either:
        - a mapping like ``{"op": "remove", "path": "/foo"}``, or
        - an existing OperationSchema instance (which will be revalidated).

        Returns:
            A concrete OperationSchema instance (e.g., ``RemoveOp(...)``).

        Notes:
            - Validation is strict (no implicit coercions).
            - Extra fields are forbidden.
            - Validation context is injected so JSONPointer fields use this registry’s pointer backend.
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
        Parse and validate a JSON Patch document from Python objects.

        A JSON Patch document is a list of operation objects. This method validates the entire list
        and returns a list of concrete OperationSchema instances.

        Example::

            ops = registry.parse_python_patch([
                {"op": "remove", "path": "/foo/bar"},
                {"op": "add", "path": "/baz", "value": 42},
            ])

        Notes:
            - Validation is strict (no implicit coercions).
            - Extra fields are forbidden.
            - Validation context is injected so JSONPointer fields use this registry’s pointer backend.
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
        Parse and validate a single operation from a JSON string/bytes payload.

        Example::

            op = registry.parse_json_op(b'{"op":"remove","path":"/foo/bar"}')

        Notes:
            - Uses strict validation (no implicit coercions).
            - Extra fields are forbidden.
            - Validation context is injected so JSONPointer fields use this registry’s pointer backend.
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
        Parse and validate a JSON Patch document from a JSON string/bytes payload.

        Example::

            ops = registry.parse_json_patch(b'''
            [
                {"op":"move","from":"/a","path":"/b"},
                {"op":"add","path":"/c","value":123}
            ]
            ''')

        Notes:
            - Uses strict validation (no implicit coercions).
            - Extra fields are forbidden.
            - Validation context is injected so JSONPointer fields use this registry’s pointer backend.
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
        """
        Return the shared standard RFC 6902 registry.

        This is a cached singleton registry containing only the built-in RFC 6902 operations.
        It uses the library’s default pointer backend.
        """
        if cls._standard is None:
            cls._standard = cls(*STANDARD_OPS)
        return cls._standard

    @classmethod
    def with_standard(
        cls,
        *extra_ops: type[OperationSchema],
        pointer_cls: type[PointerBackend] = _DEFAULT_POINTER_CLS,
    ) -> Self:
        """
        Create a registry containing the standard RFC 6902 ops plus additional custom operations.

        Args:
            extra_ops:
                One or more custom OperationSchema subclasses.

            pointer_cls:
                Optional pointer backend override used when validating JSONPointer fields.

        Returns:
            A new OperationRegistry instance (not cached).
        """
        return cls(*STANDARD_OPS, *extra_ops, pointer_cls=pointer_cls)

    @override
    def __hash__(self) -> int:
        """
        Best-effort structural hash.

        The hash incorporates the registry's operation set and pointer backend class so registries
        can be used as dictionary keys in higher-level wrappers.

        Notes:
            This is not an identity hash. Two registries with the same operation set and pointer backend
            will hash the same, even if they are distinct instances.
        """
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
