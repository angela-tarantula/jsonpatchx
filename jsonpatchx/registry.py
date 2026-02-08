from collections import Counter
from collections.abc import Mapping, Sequence
from inspect import isabstract, isclass
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Generic,
    TypeAliasType,
    TypeVarTuple,
    Union,
    Unpack,
    cast,
    overload,
    override,
)

from pydantic import Field, TypeAdapter
from typing_extensions import TypeVar

from jsonpatchx.backend import (
    _DEFAULT_POINTER_CLS,
    PointerBackend,
    _PointerClassProtocol,
    _validate_backend_class,
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
from jsonpatchx.exceptions import InvalidOperationRegistry
from jsonpatchx.pointer import (
    _JSONPOINTER_POINTER_BACKEND_CTX_KEY,
    _JSONPOINTER_VALIDATION_CTX_LITERALS,
)
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue

type AnyRegistry = GenericOperationRegistry[*tuple[Any, ...]]
Ops = TypeVarTuple("Ops")  # bound=type[OperationSchema] | type[AnyRegistry]
PBT = TypeVar("PBT", bound=PointerBackend)

_REGISTRY_CACHE: dict[
    tuple[tuple[type[OperationSchema], ...], type[_PointerClassProtocol]],
    type[AnyRegistry],
] = {}


class _RegistryMeta(type):
    @override
    def __call__(cls, *args: object, **kwargs: object) -> None:
        raise TypeError(
            f"{cls.__name__} is a registry type and cannot be instantiated. "
            "Use it directly or via OperationRegistry[Op1, Op2, ...]."
        )

    @staticmethod
    def _registry_type_name(
        ops: tuple[type[OperationSchema], ...],
        pointer_cls: type[_PointerClassProtocol],
    ) -> str:
        if (
            ops == GenericOperationRegistry._deterministic_sort(*STANDARD_OPS)
            and pointer_cls is PointerBackend
        ):
            return "StandardRegistry"
        op_names = "_".join(op.__name__ for op in ops)
        if pointer_cls is PointerBackend:
            return f"OperationRegistry_{op_names}"
        return f"GenericOperationRegistry_{op_names}__{pointer_cls.__name__}"

    @staticmethod
    def _registry_display_name(
        ops: tuple[type[OperationSchema], ...],
        pointer_cls: type[_PointerClassProtocol],
    ) -> str:
        op_names = ", ".join(op.__name__ for op in ops)
        if pointer_cls is PointerBackend:
            return f"OperationRegistry[{op_names}]"
        return f"GenericOperationRegistry[{op_names}, {pointer_cls.__name__}]"

    @override
    def __repr__(cls) -> str:
        if cls is GenericOperationRegistry or cls is OperationRegistry:
            return cls.__name__
        assert hasattr(cls, "ops"), "internal error: OperationRegistry"
        assert hasattr(cls, "_pointer_cls"), "internal error: OperationRegistry"
        return _RegistryMeta._registry_display_name(cls.ops, cls._pointer_cls)


class GenericOperationRegistry(Generic[*Ops, PBT], metaclass=_RegistryMeta):
    """
    Registry for JSON Patch operation types with a custom JSON Pointer.

    >>> DotPointerRegistry = GenericOperationRegistry[AddOp, RemoveOp, DotPointer]
    >>> LogRegistry = GenericOperationRegistry[StandardRegistry, IncrementOp, LogPointer]
    """

    # Normally, ClassVars can't be generic (https://github.com/python/typing/discussions/1424#discussioncomment-7989934)
    # But in this case, GenericOperationRegistry[A] and GenericOperationRegistry[B] are different runtime objects.
    ops: ClassVar[tuple[type[OperationSchema], ...]]
    _pointer_cls: ClassVar[type[_PointerClassProtocol]]
    union: ClassVar[TypeAliasType]
    _model_map: ClassVar[Mapping[str, type[OperationSchema]]]
    _op_adapter: ClassVar[TypeAdapter[OperationSchema]]
    _patch_adapter: ClassVar[TypeAdapter[list[OperationSchema]]]
    _ctx: ClassVar[
        dict[_JSONPOINTER_VALIDATION_CTX_LITERALS, type[_PointerClassProtocol]]
    ]

    @overload
    def __class_getitem__(cls, params: tuple[Unpack[Ops]]) -> type[AnyRegistry]: ...

    @overload
    def __class_getitem__(
        cls, params: tuple[Unpack[Ops], type[PBT]]
    ) -> type[AnyRegistry]: ...

    def __class_getitem__(cls, params: object) -> type[AnyRegistry]:
        op_models, pointer_cls = cls._split_ops_and_pointer(params)
        ordered_ops = cls._deterministic_sort(*op_models)
        cache_key = (ordered_ops, pointer_cls)
        cached = _REGISTRY_CACHE.get(cache_key)
        if cached is not None:
            return cached

        model_map = cls._build_model_map(*ordered_ops)
        union_type, op_adapter, patch_adapter = cls._build_adapters(*ordered_ops)
        ctx_backend = (
            _DEFAULT_POINTER_CLS if pointer_cls is PointerBackend else pointer_cls
        )
        ctx: dict[_JSONPOINTER_VALIDATION_CTX_LITERALS, type[_PointerClassProtocol]] = {
            _JSONPOINTER_POINTER_BACKEND_CTX_KEY: ctx_backend
        }

        name = cls._registry_type_name(ordered_ops, pointer_cls)
        namespace = {
            "ops": ordered_ops,
            "_pointer_cls": pointer_cls,
            "union": union_type,
            "_model_map": model_map,
            "_op_adapter": op_adapter,
            "_patch_adapter": patch_adapter,
            "_ctx": ctx,
        }
        registry_type = type(name, (cls,), namespace)
        _REGISTRY_CACHE[cache_key] = registry_type
        return registry_type

    @classmethod
    def _split_ops_and_pointer(
        cls,
        params: object,
    ) -> tuple[tuple[type[OperationSchema], ...], type[_PointerClassProtocol]]:
        if not params or not isinstance(params, tuple):
            raise InvalidOperationRegistry(f"Invalid registry params: {params!r}")
        variadic_params = cast(tuple[object], params[:-1])
        last_param = cast(object, params[-1])

        pointer_cls = _validate_backend_class(last_param)

        op_models, pointer_cls = cls._validate_variadic_params(
            variadic_params, pointer_cls
        )
        cls._validate_op_name_uniqueness(
            *op_models
        )  # NOTE TO SELF: put this in schemas.py?
        return op_models, pointer_cls  # NOTE TO SELF: changed None -> PointerBackend

    @staticmethod
    def _validate_variadic_params(
        variadic_params: tuple[object, ...],
        pointer_cls: type[_PointerClassProtocol],
    ) -> tuple[tuple[type[OperationSchema], ...], type[_PointerClassProtocol]]:
        op_models: list[type[OperationSchema]] = []
        registry_pointer_classes: set[type[_PointerClassProtocol]] = (
            set()
        )  # NOTE TO SELF: used to be type[PBT] |none

        for param in variadic_params:
            if not isclass(param):
                raise InvalidOperationRegistry(f"{param!r} is not a class")

            if issubclass(param, GenericOperationRegistry):
                registry = param
                op_models.extend(registry.ops)
                registry_pointer_classes.add(registry._pointer_cls)
                continue

            if not issubclass(param, OperationSchema) or isabstract(param):
                raise InvalidOperationRegistry(
                    f"{param!r} is not an concrete OperationSchema"
                )
            op_model = param
            op_models.append(op_model)

        if pointer_cls is PointerBackend:
            if registry_pointer_classes and registry_pointer_classes != set(
                [PointerBackend]
            ):
                raise InvalidOperationRegistry(
                    f"Expected standard operation registries, got generics: {[ptr_cls for ptr_cls in registry_pointer_classes if ptr_cls is not PointerBackend]}"
                )
        else:
            for nested_ptr_cls in registry_pointer_classes:
                if nested_ptr_cls is not PointerBackend and not issubclass(
                    pointer_cls, nested_ptr_cls
                ):
                    raise InvalidOperationRegistry(
                        f"operation pointer class {nested_ptr_cls!r} cannot be stricter than registry pointer class {pointer_cls!r}"
                    )  # NOTE: do same check with operationschema.ptr's (?)

        return tuple(op_models), pointer_cls

    @staticmethod
    def _validate_op_name_uniqueness(*op_models: type[OperationSchema]) -> None:
        """The __name__ of every op must be unique for the Registry's type name."""
        if not op_models:
            raise InvalidOperationRegistry("At least one OperationSchema is required")
        name_counts = Counter(op_model.__name__ for op_model in op_models)
        non_unique_names = {name for name, cnt in name_counts.items() if cnt > 1}
        if non_unique_names:
            raise InvalidOperationRegistry(
                f"Expected unique OperationSchema names, got duplicates for these: {non_unique_names!r}"
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
            GenericOperationRegistry._deterministic_sort(*op_models)
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
        return tuple(  # deterministic ordering of ops in OpenAPI
            sorted(op_models, key=lambda op: op._op_literals[0])
        )

    @classmethod
    def ops_by_name(cls) -> Mapping[str, type[OperationSchema]]:
        return cls._model_map

    @classmethod
    def ops_set(cls) -> frozenset[type[OperationSchema]]:
        return frozenset(cls._model_map.values())

    @classmethod
    def parse_python_op(
        cls, obj: Mapping[str, JSONValue] | OperationSchema
    ) -> OperationSchema:
        return cls._op_adapter.validate_python(
            obj,
            strict=True,
            by_alias=True,
            by_name=False,
            context=cls._ctx,
        )

    @classmethod
    def parse_python_patch(
        cls, python: Sequence[OperationSchema | Mapping[str, JSONValue]]
    ) -> list[OperationSchema]:
        return cls._patch_adapter.validate_python(
            python,
            strict=True,
            by_alias=True,
            by_name=False,
            context=cls._ctx,
        )

    @classmethod
    def parse_json_op(cls, text: str | bytes | bytearray) -> OperationSchema:
        return cls._op_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
            context=cls._ctx,
        )

    @classmethod
    def parse_json_patch(cls, text: str | bytes | bytearray) -> list[OperationSchema]:
        return cls._patch_adapter.validate_json(
            text,
            strict=True,
            by_alias=True,
            by_name=False,
            context=cls._ctx,
        )


# A statement like ``type OperationRegistry[*Ops] = GenericOperationRegistry[*Ops, PointerBackend]``
# creates a typing.TypeAliasType at runtime, not an actual class, so it would lack the metaclass
# machinery (__class_getitem__, registry caching, etc.) that the runtime relies on.
if TYPE_CHECKING:
    # Mypy only needs a generic alias form, but at runtime a concrete class is necessary to inject the
    # default pointer backend into __class_getitem__.
    class OperationRegistry(GenericOperationRegistry[*Ops, PointerBackend]):
        """
        Registry for JSON Patch operation types.

        >>> LimitedRegistry = OperationRegistry[AddOp, RemoveOp]
        >>> ExpandedRegistry = OperationRegistry[StandardRegistry, ToggleOp]
        """
else:

    class OperationRegistry(GenericOperationRegistry):
        @override
        @classmethod
        def _split_ops_and_pointer(
            cls,
            params: object,
        ) -> tuple[tuple[type[OperationSchema], ...], type[_PointerClassProtocol]]:
            if not isinstance(params, tuple):
                params = (params, PointerBackend)
            else:
                params = (*params, PointerBackend)
            return super()._split_ops_and_pointer(params)


StandardRegistry = OperationRegistry[AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp]

if TYPE_CHECKING:
    _dont_raise_mypy_error_1 = GenericOperationRegistry[AddOp, _DEFAULT_POINTER_CLS]

    # from jsonpath import JSONPointer as ExtendedJsonPointer

    # _dont_raise_mypy_error_2 = GenericOperationRegistry[AddOp, ExtendedJsonPointer]
