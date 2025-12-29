from typing import Any, ClassVar, Generic, Self, TypeAliasType, TypeVar, cast, override

from pydantic import BaseModel, ConfigDict, RootModel, create_model

from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.standard import _apply_ops
from jsonpatch.types import _JSON_VALUE_ADAPTER, JSONValue

ModelT = TypeVar("ModelT", bound=BaseModel)


class _RegistryBoundPatchRoot(RootModel[Any]):
    """
    RootModel base that automatically injects the registry context needed for custom PointerBackends.
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
    RootModel patch type for patching Pydantic models.

    Subclasses must set:
      - __target_model__: the Pydantic model being patched
      - __registry__: the registry used to validate ops
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
        patched = _apply_ops(self.ops, data)
        return self.__target_model__.model_validate(patched)


class JsonPatchFor(Generic[ModelT]):
    """
    Factory:
      JsonPatchFor[User]
      JsonPatchFor[(User, registry)]
    Produces a RootModel whose JSON shape is a top-level array of ops.
    """

    def __class_getitem__(
        cls, param: type[BaseModel] | tuple[type[BaseModel], OperationRegistry]
    ) -> type[_BasePatchModel]:
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
        """Dynamically create the Pydantic model class."""
        registry_union: TypeAliasType = registry.union  # runtime discriminated union

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
    RootModel patch type for patching plain JSON documents.
    Subclasses must set __registry__.
    """

    def apply(self, doc: JSONValue, *, validate_doc: bool = False) -> JSONValue:
        if validate_doc:
            _JSON_VALUE_ADAPTER.validate_python(doc, strict=True)
        return _apply_ops(self.ops, doc)


def make_json_patch_body(
    registry: OperationRegistry | None = None,
    *,
    name: str | None = None,
) -> type[_BasePatchBody]:
    """
    Factory for FastAPI request-body models whose JSON shape is: [ {op...}, {op...}, ... ].
    """

    registry = registry or OperationRegistry.standard()
    registry_union: TypeAliasType = registry.union  # runtime discriminated union

    PatchBody = create_model(
        name or "JsonPatchBody",
        __base__=_BasePatchBody,
        root=(list[registry_union], ...),  # type: ignore[valid-type]
    )

    PatchBody.__registry__ = registry
    return PatchBody
