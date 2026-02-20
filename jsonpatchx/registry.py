import copy
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
    cast,
    get_args,
    get_origin,
    get_type_hints,
    override,
)

from pydantic import Field, TypeAdapter, create_model
from typing_extensions import TypeForm, TypeVar

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
from jsonpatchx.exceptions import InvalidOperationRegistry, OperationNotRecognized
from jsonpatchx.pointer import (
    _JSONPOINTER_POINTER_BACKEND_CTX_KEY,
    _JSONPOINTER_VALIDATION_CTX_LITERALS,
    JSONPointer,
)
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue

type AnyRegistry = GenericOperationRegistry[PointerBackend, *tuple[Any, ...]]
Ops = TypeVarTuple("Ops")  # bound=type[OperationSchema]
PBT = TypeVar("PBT", bound=PointerBackend, covariant=True)

_REGISTRY_CACHE: dict[
    tuple[tuple[type[OperationSchema], ...], type[_PointerClassProtocol]],
    type[AnyRegistry],
] = {}
_SPECIALIZED_OP_CACHE: dict[
    tuple[type[OperationSchema], type[_PointerClassProtocol]],
    type[OperationSchema],
] = {}
_TYPEVAR_RUNTIME_TYPE = type(TypeVar("_PointerBackendTypeVarProbe"))


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
            and pointer_cls is _DEFAULT_POINTER_CLS
        ):
            return "StandardRegistry"
        op_names = "_".join(op.__name__ for op in ops)
        if pointer_cls is _DEFAULT_POINTER_CLS:
            return f"OperationRegistry_{op_names}"
        return f"GenericOperationRegistry_{pointer_cls.__name__}__{op_names}"

    @staticmethod
    def _registry_display_name(
        ops: tuple[type[OperationSchema], ...],
        pointer_cls: type[_PointerClassProtocol],
    ) -> str:
        op_names = ", ".join(op.__name__ for op in ops)
        if pointer_cls is _DEFAULT_POINTER_CLS:
            return f"OperationRegistry[{op_names}]"
        return f"GenericOperationRegistry[{pointer_cls.__name__}, {op_names}]"

    @override
    def __repr__(cls) -> str:
        if cls is GenericOperationRegistry or cls is OperationRegistry:
            return cls.__name__
        assert hasattr(cls, "ops"), "internal error: OperationRegistry"
        assert hasattr(cls, "_pointer_cls"), "internal error: OperationRegistry"
        return _RegistryMeta._registry_display_name(cls.ops, cls._pointer_cls)


class GenericOperationRegistry(Generic[PBT, *Ops], metaclass=_RegistryMeta):
    """
    Registry for JSON Patch operation types with a custom JSON Pointer.

    >>> DotPointerRegistry = GenericOperationRegistry[DotPointer, AddOp, RemoveOp]
    >>> LogRegistry = GenericOperationRegistry[LogPointer, AddOp, IncrementOp]
    """

    # Normally, ClassVars can't be generic (https://github.com/python/typing/discussions/1424#discussioncomment-7989934)
    # But in this case, GenericOperationRegistry[A] and GenericOperationRegistry[B] are different runtime objects.
    ops: ClassVar[tuple[type[OperationSchema], ...]]
    _pointer_cls: ClassVar[type[_PointerClassProtocol]]
    union: ClassVar[TypeAliasType]
    _bound_ops_set: ClassVar[frozenset[type[OperationSchema]]]
    _accepted_ops_set: ClassVar[frozenset[type[OperationSchema]]]
    _model_map: ClassVar[Mapping[str, type[OperationSchema]]]
    _op_adapter: ClassVar[TypeAdapter[OperationSchema]]
    _patch_adapter: ClassVar[TypeAdapter[list[OperationSchema]]]
    _ctx: ClassVar[
        dict[_JSONPOINTER_VALIDATION_CTX_LITERALS, type[_PointerClassProtocol]]
    ]

    def __class_getitem__(cls, params: object) -> type[AnyRegistry]:
        op_models, pointer_cls = cls._split_ops_and_pointer(params)
        ordered_ops = cls._deterministic_sort(*op_models)
        bound_ops = cls._bind_op_models(pointer_cls, *ordered_ops)
        cache_key = (ordered_ops, pointer_cls)
        cached = _REGISTRY_CACHE.get(cache_key)
        if cached is not None:
            return cached

        model_map = cls._build_model_map(*bound_ops)
        union_type, op_adapter, patch_adapter = cls._build_adapters(*bound_ops)
        ctx: dict[_JSONPOINTER_VALIDATION_CTX_LITERALS, type[_PointerClassProtocol]] = {
            _JSONPOINTER_POINTER_BACKEND_CTX_KEY: pointer_cls
        }

        name = cls._registry_type_name(ordered_ops, pointer_cls)
        namespace = {
            "ops": ordered_ops,
            "_bound_ops_set": frozenset(bound_ops),
            "_accepted_ops_set": frozenset((*ordered_ops, *bound_ops)),
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
        if not isinstance(params, tuple) or len(params) < 2:
            raise InvalidOperationRegistry(f"Invalid registry params: {params!r}")
        first_param = cast(object, params[0])
        variadic_params = cast(tuple[object, ...], params[1:])

        pointer_cls = _validate_backend_class(first_param)
        op_models = cls._validate_op_models(variadic_params)
        cls._validate_op_name_uniqueness(*op_models)
        return op_models, pointer_cls

    @staticmethod
    def _validate_op_models(
        unverified_params: tuple[object, ...],
    ) -> tuple[type[OperationSchema], ...]:
        for param in unverified_params:
            if not isclass(param):
                raise InvalidOperationRegistry(f"{param!r} is not a class")

            if not issubclass(param, OperationSchema) or isabstract(param):
                raise InvalidOperationRegistry(
                    f"{param!r} is not a concrete OperationSchema"
                )
        return cast(tuple[type[OperationSchema], ...], unverified_params)

    @staticmethod
    def _validate_op_name_uniqueness(*op_models: type[OperationSchema]) -> None:
        """The __name__ of every op must be unique for the Registry's type name."""
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
        """Deterministic sorting of OperationSchemas for OpenAPI reproducibility."""
        return tuple(sorted(op_models, key=lambda op: op._op_literals[0]))

    @classmethod
    def _bind_op_models(
        cls,
        pointer_cls: type[_PointerClassProtocol],
        *op_models: type[OperationSchema],
    ) -> tuple[type[OperationSchema], ...]:
        return tuple(
            cls._bind_op_model_pointer_backend(op_model, pointer_cls)
            for op_model in op_models
        )

    @classmethod
    def _bind_op_model_pointer_backend(
        cls,
        op_model: type[OperationSchema],
        pointer_cls: type[_PointerClassProtocol],
    ) -> type[OperationSchema]:
        cache_key = (op_model, pointer_cls)
        cached = _SPECIALIZED_OP_CACHE.get(cache_key)
        if cached is not None:
            return cached

        type_hints = cast(
            dict[str, TypeForm[Any]], get_type_hints(op_model, include_extras=True)
        )
        field_overrides: dict[str, tuple[object, object]] = {}

        for field_name, field_info in op_model.model_fields.items():
            annotation = type_hints.get(field_name)
            if annotation is None:
                raise InvalidOperationRegistry(
                    f"{op_model.__name__}.{field_name} is missing a resolved type annotation; "
                    "cannot specialize pointer backend"
                )
            specialized_annotation = cls._specialize_pointer_annotation(
                annotation,
                pointer_cls,
                op_model=op_model,
                field_name=field_name,
            )
            if specialized_annotation == annotation:
                continue
            field_overrides[field_name] = (
                specialized_annotation,
                copy.deepcopy(field_info),
            )

        if not field_overrides:
            _SPECIALIZED_OP_CACHE[cache_key] = op_model
            return op_model

        bound_op_model = create_model(
            f"{op_model.__name__}__{pointer_cls.__name__}Bound",
            __base__=op_model,
            **cast(dict[str, Any], field_overrides),
        )
        _SPECIALIZED_OP_CACHE[cache_key] = bound_op_model
        return bound_op_model

    @classmethod
    def _specialize_pointer_annotation(
        cls,
        annotation: TypeForm[Any],
        pointer_cls: type[_PointerClassProtocol],
        *,
        op_model: type[OperationSchema],
        field_name: str,
    ) -> TypeForm[Any]:
        origin = get_origin(annotation)
        if isinstance(origin, type) and issubclass(origin, JSONPointer):
            pointer_args = cast(tuple[TypeForm[Any], ...], get_args(annotation))
            if len(pointer_args) == 1:
                # JSONPointer[T]
                type_param = pointer_args[0]
                return cast(
                    TypeForm[Any],
                    origin[type_param, pointer_cls],  # type: ignore[index]
                )
            else:
                # JSONPointr[T, P] or more args
                type_param, backend_param, *extra_args = pointer_args
                validated_backend = cls._resolve_backend_param_for_registry(
                    backend_param,
                    pointer_cls,
                    op_model=op_model,
                    field_name=field_name,
                )
                rewritten_args = (type_param, validated_backend, *extra_args)
                return cast(TypeForm[Any], origin[rewritten_args])  # type: ignore[index]

        if origin is Annotated:
            annotation_args = cast(tuple[TypeForm[Any], ...], get_args(annotation))
            if not annotation_args:
                return annotation
            base_annotation, *metadata = annotation_args
            specialized_base = cls._specialize_pointer_annotation(
                base_annotation,
                pointer_cls,
                op_model=op_model,
                field_name=field_name,
            )
            if specialized_base == base_annotation:
                return annotation
            return cast(TypeForm[Any], Annotated[specialized_base, *metadata])

        return annotation

    @classmethod
    def _resolve_backend_param_for_registry(
        cls,
        backend_param: object,
        registry_backend: type[_PointerClassProtocol],
        *,
        op_model: type[OperationSchema],
        field_name: str,
    ) -> type[_PointerClassProtocol]:
        if backend_param is _DEFAULT_POINTER_CLS:
            return registry_backend

        if isinstance(backend_param, _TYPEVAR_RUNTIME_TYPE):
            if not cls._is_backend_typevar_compatible(backend_param, registry_backend):
                raise InvalidOperationRegistry(
                    f"{op_model.__name__}.{field_name} backend type parameter "
                    f"{backend_param!r} is incompatible with registry backend "
                    f"{registry_backend.__name__}"
                )
            return registry_backend

        bound_backend = _validate_backend_class(backend_param)
        if not issubclass(registry_backend, bound_backend):
            return bound_backend
        return registry_backend

    @staticmethod
    def _is_backend_typevar_compatible(
        backend_typevar: object,
        registry_backend: type[_PointerClassProtocol],
    ) -> bool:
        constraints = cast(
            tuple[object, ...], getattr(backend_typevar, "__constraints__")
        )
        if constraints:
            validated_constraints = tuple(
                _validate_backend_class(c) for c in constraints
            )
            return any(
                issubclass(registry_backend, constraint)
                for constraint in validated_constraints
            )
        bound = getattr(backend_typevar, "__bound__", None)
        if bound is None:
            return False
        validated_bound = _validate_backend_class(bound)
        return issubclass(registry_backend, validated_bound)

    @classmethod
    def ops_by_name(cls) -> Mapping[str, type[OperationSchema]]:
        return cls._model_map

    @classmethod
    def ops_set(cls) -> frozenset[type[OperationSchema]]:
        return cls._accepted_ops_set

    @classmethod
    def parse_python_op(
        cls, obj: Mapping[str, JSONValue] | OperationSchema
    ) -> OperationSchema:
        if isinstance(obj, OperationSchema):
            if type(obj) not in cls._accepted_ops_set:
                raise OperationNotRecognized(
                    f"Operation {type(obj).__name__} is not allowed in this registry"
                )
            if type(obj) in cls._bound_ops_set:
                return obj
            return cls._op_adapter.validate_python(
                obj.model_dump(mode="json", by_alias=True),
                strict=True,
                by_alias=True,
                by_name=False,
                context=cls._ctx,
            )
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
        ops: list[OperationSchema] = []
        for item in python:
            if isinstance(item, OperationSchema):
                if type(item) not in cls._accepted_ops_set:
                    raise OperationNotRecognized(
                        f"Operation {type(item).__name__} is not allowed in this registry"
                    )
                if type(item) in cls._bound_ops_set:
                    ops.append(item)
                else:
                    ops.append(
                        cls._op_adapter.validate_python(
                            item.model_dump(mode="json", by_alias=True),
                            strict=True,
                            by_alias=True,
                            by_name=False,
                            context=cls._ctx,
                        )
                    )
            else:
                ops.append(
                    cls._op_adapter.validate_python(
                        item,
                        strict=True,
                        by_alias=True,
                        by_name=False,
                        context=cls._ctx,
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


# A statement like ``type OperationRegistry[*Ops] = GenericOperationRegistry[_DEFAULT_POINTER_CLS, *Ops]``
# creates a typing.TypeAliasType at runtime, not an actual class, so it would lack the metaclass
# machinery (__class_getitem__, registry caching, etc.) that the runtime relies on.
if TYPE_CHECKING:
    # Mypy only needs a generic alias form, but at runtime a concrete class is necessary to inject the
    # default pointer backend into __class_getitem__.
    class OperationRegistry(GenericOperationRegistry[_DEFAULT_POINTER_CLS, *Ops]):
        """
        Registry for JSON Patch operation types.

        >>> LimitedRegistry = OperationRegistry[AddOp, RemoveOp]
        >>> ExpandedRegistry = OperationRegistry[AddOp, RemoveOp, ToggleOp]
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
                params = (_DEFAULT_POINTER_CLS, params)
            else:
                params = (_DEFAULT_POINTER_CLS, *params)
            return super()._split_ops_and_pointer(params)


StandardRegistry = OperationRegistry[AddOp, CopyOp, MoveOp, RemoveOp, ReplaceOp, TestOp]

if TYPE_CHECKING:
    _dont_raise_mypy_error_1 = GenericOperationRegistry[_DEFAULT_POINTER_CLS, AddOp]

    # from jsonpath import JSONPointer as ExtendedJsonPointer

    # _dont_raise_mypy_error_2 = GenericOperationRegistry[ExtendedJsonPointer, AddOp]
