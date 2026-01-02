from typing import Any, ClassVar, Self, TypeAliasType, cast, override

from pydantic import BaseModel, ConfigDict, RootModel, create_model

from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.standard import _apply_ops
from jsonpatch.types import _JSON_VALUE_ADAPTER, JSONValue


def _named_union(name: str, union: TypeAliasType) -> TypeAliasType:
    """Dynamically name each patch model's union type for clearer OpenAPI output."""
    return TypeAliasType(name, union.__value__)


class _RegistryBoundPatchRoot(RootModel[Any]):
    """
    Internal base for registry-backed JSON Patch RootModels.

    Notes:
        - ``root`` is a JSON Patch document: ``list[registry.union]`` built dynamically via
          ``create_model``.
        - ``__registry__`` is set on subclasses.
        - ``model_validate`` and ``model_validate_json`` inject ``context=__registry__._ctx`` unless the
          caller already provided ``context``. This ensures ``JSONPointer[...]`` fields are created with
          the registry's configured pointer backend.
    """

    # Choice: This base intentionally uses RootModel[Any].
    # Why: The concrete root type (list[registry.union]) is supplied dynamically
    #      by factories via create_model(). Making this generic would either lie
    #      to the type checker or require pervasive casting with no real benefit.

    model_config = ConfigDict(frozen=True, strict=True)

    __registry__: ClassVar[OperationRegistry]

    @property
    def ops(self) -> list[OperationSchema]:
        # Assumption: subclasses will set root to list[registry.union]
        return cast(list[OperationSchema], self.root)

    @classmethod
    @override
    def model_validate(cls, obj: Any, **kwargs: Any) -> Self:
        # Assumption: callers who do provide context know what they're doing
        #             (or else the PointerBackend context injection silently doesn't happen)
        kwargs.setdefault("context", cls.__registry__._ctx)
        return super().model_validate(obj, **kwargs)

    @classmethod
    @override
    def model_validate_json(
        cls, json_data: str | bytes | bytearray, **kwargs: Any
    ) -> Self:
        # Assumption: callers who do provide context know what they're doing
        #             (or else the PointerBackend context injection silently doesn't happen)
        kwargs.setdefault("context", cls.__registry__._ctx)
        return super().model_validate_json(json_data, **kwargs)


class _BasePatchModel(_RegistryBoundPatchRoot):
    """
    Internal patch RootModel for model-aware patching (Pydantic BaseModel targets).

    Notes:
        - ``apply(target)`` patches ``target.model_dump()`` using the shared engine.
        - The patched output is validated back into ``__target_model__`` via ``model_validate``.
        - The input model instance is not mutated.
    """

    __target_model__: ClassVar[type[BaseModel]]

    def apply(self, target: BaseModel) -> BaseModel:
        if not isinstance(target, BaseModel):
            raise TypeError(
                f"{self.__class__.__name__}.apply() expects a Pydantic BaseModel instance, "
                f"got {type(target).__name__}"
            )
        if not self.ops:
            return target
        data = target.model_dump()
        patched = _apply_ops(self.ops, data, inplace=True)
        return self.__target_model__.model_validate(patched)


class JsonPatchFor[ModelT: BaseModel]:
    """
    Factory for creating typed JSON Patch models for a specific Pydantic model.

    This is intended for endpoints and internal APIs where:

    - the request body is a standard JSON Patch document (a JSON array of ops),
    - you want OpenAPI to show each operation as a first-class discriminated type,
    - and you want an ergonomic ``.apply(model_instance)`` method.

    Example:
        Standard RFC 6902 operations:

    >>> UserPatch = JsonPatchFor[User]
    >>> patch = UserPatch.model_validate(
    ...     [{"op": "replace", "path": "/name", "value": "Angela"}]
    ... )
    >>> updated_user = patch.apply(user)

        Custom operations or pointer backend (registry-scoped):

    >>> registry = OperationRegistry.with_standard(IncrementOp, pointer_cls=MyPointer)
    >>> UserPatch = JsonPatchFor[(User, registry)]

    Notes:
        ``JsonPatchFor[...]`` accepts either ``JsonPatchFor[MyModel]`` (standard registry) or
        ``JsonPatchFor[(MyModel, registry)]`` (explicit ``OperationRegistry``). The returned type is a
        dynamically generated ``pydantic.RootModel`` subclass whose JSON shape is a top-level list.
    """

    def __class_getitem__(
        cls, param: type[BaseModel] | tuple[type[BaseModel], OperationRegistry]
    ) -> type[_BasePatchModel]:
        """
        Create a registry-bound patch RootModel type for the given target model.

        This is the implementation behind ``JsonPatchFor[Model]`` and
        ``JsonPatchFor[(Model, registry)]``.
        """
        if isinstance(param, tuple):
            if len(param) != 2:
                raise TypeError(
                    "JsonPatchFor[(Model, registry)] expects exactly two items"
                )
            model, registry = param
        else:
            model, registry = param, OperationRegistry.standard()

        # Verify that model is a BaseModel subclass. Must verify that model is a type first or else issubclass complains.
        if not isinstance(model, type) or not issubclass(model, BaseModel):  # type: ignore[redundant-expr]
            raise TypeError(
                f"JsonPatchFor[...] expects a Pydantic BaseModel, got {model!r}"
            )

        if not isinstance(registry, OperationRegistry):
            raise TypeError(
                "JsonPatchFor[(Model, registry)] second argument must be an OperationRegistry, "
                f"got {type(registry).__name__}"
            )

        return cls._create_patch_model(model, registry)

    @staticmethod
    def _create_patch_model(
        model: type[BaseModel],
        registry: OperationRegistry,
    ) -> type[_BasePatchModel]:
        """
        Internal: build the concrete RootModel subclass used for the patch request body.

        The generated model's root type is ``list[registry.union]`` so Pydantic can parse a
        JSON Patch document into typed operations using discriminated-union dispatch.
        """
        registry_union: TypeAliasType = _named_union(
            f"{model.__name__}PatchOperation", registry.union
        )

        PatchModel = create_model(
            f"{model.__name__}Patch",
            __base__=_BasePatchModel,
            root=(list[registry_union], ...),  # type: ignore[valid-type]
        )

        PatchModel.__target_model__ = model
        PatchModel.__registry__ = registry
        return PatchModel


class _BasePatchBody(_RegistryBoundPatchRoot):
    """
    Internal patch RootModel for typed operations applied to an untyped JSON document.

    Notes:
        - ``apply(doc, inplace=...)`` delegates to ``_apply_ops`` (engine defines copy and mutation semantics).
        - Optional ``validate_doc=True`` validates that ``doc`` is a strict JSON value before patching.
    """

    def apply(
        self, doc: JSONValue, *, validate_doc: bool = False, inplace: bool = False
    ) -> JSONValue:
        if validate_doc:
            _JSON_VALUE_ADAPTER.validate_python(doc, strict=True)
        return _apply_ops(self.ops, doc, inplace=inplace)


def make_json_patch_body(
    registry: OperationRegistry | None = None,
    *,
    name: str = "JsonPatchBody",
) -> type[_BasePatchBody]:
    """
    Create a Pydantic model type suitable for a FastAPI request body representing a JSON Patch.

    The returned model is a dynamically generated ``pydantic.RootModel`` subclass whose JSON
    representation is a top-level array of operations (a standard JSON Patch document).

    This is the recommended API when you want:

    - typed operations (including custom ops) with OpenAPI support
    - a plain JSON document as the patch target (dict/list/primitives)
    - an ergonomic ``patch.apply(doc)`` method in your endpoint

    Example:
        Typed ops applied to an untyped document:

        >>> registry = OperationRegistry.with_standard(IncrementOp)
        >>> CustomPatchBody = make_json_patch_body(registry, name="Custom")

        >>> @app.patch("/configs/{config_id}")
        ... def patch_config(config_id: str, patch: CustomPatchBody):
        ...     doc = load_config(config_id)
        ...     updated = patch.apply(doc)
        ...     save_config(config_id, updated)
        ...     return updated

    Args:
        registry: OperationRegistry used to validate and parse operations. Defaults to the standard
            RFC 6902 registry.
        name: Optional name of the generated model class. Naming the class can improve OpenAPI output.

    Notes:
        - The registry's validation context is automatically injected during parsing so ``JSONPointer``
          fields can use the registry's configured pointer backend.
        - Create these model types at import time (module scope) so FastAPI/OpenAPI sees a stable schema.
    """

    registry = registry or OperationRegistry.standard()
    registry_union: TypeAliasType = _named_union(
        f"{name}PatchOperation", registry.union
    )

    PatchBody = create_model(
        f"{name}Patch",
        __base__=_BasePatchBody,
        __config__=ConfigDict(
            frozen=True,
            strict=True,
            json_schema_extra={
                "description": "RFC 6902 JSON Patch document (list of operations).",
                "examples": [
                    [{"op": "replace", "path": "/name", "value": "Angela"}],
                    [{"op": "add", "path": "/tags/-", "value": "staff"}],
                ],
            },
        ),
        root=(list[registry_union], ...),  # type: ignore[valid-type]
    )

    PatchBody.__registry__ = registry
    PatchBody.__doc__ = "RFC 6902 JSON Patch document (list of operations)."
    return PatchBody
