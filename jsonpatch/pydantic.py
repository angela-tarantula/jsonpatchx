from typing import ClassVar, Generic, Type, TypeAliasType, TypeVar

from pydantic import BaseModel, ConfigDict, create_model

from jsonpatch.exceptions import InvalidJsonPatch
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.standard import _apply_ops

ModelT = TypeVar("ModelT", bound=BaseModel)


class _BasePatchModel(BaseModel):
    """
    Base class for all dynamically-created JsonPatchFor[...] models.

    Each subclass is expected to have:

    - __root__: list[registry.union]
    - __target_model__: the Pydantic model type being patched
    - __registry__: the OperationRegistry used for parsing ops
    """

    model_config = ConfigDict(frozen=True)

    __target_model__: ClassVar[Type[BaseModel]]
    __registry__: ClassVar[OperationRegistry]

    def apply(self, target: BaseModel) -> BaseModel:
        """Apply this patch to a Pydantic model instance."""
        if not isinstance(target, BaseModel):
            raise TypeError(
                f"{self.__class__.__name__}.apply() expects a Pydantic BaseModel "
                f"instance, got {type(target).__name__}"
            )
        try:
            ops: list[OperationSchema] = self.__root__  # type: ignore[attr-defined]
            assert isinstance(ops, list)
        except (AttributeError, AssertionError) as e:  # defensive
            raise InvalidJsonPatch("Patch Model is malformed") from e

        data = target.model_dump()
        patched = _apply_ops(ops, data)
        return self.__target_model__.model_validate(patched)


class JsonPatchFor(Generic[ModelT]):
    """
    JsonPatchFor[User]                      -> uses standard RFC 6902 registry
    JsonPatchFor[(User, registry)]          -> uses a custom OperationRegistry

    Returns a dynamically-generated Pydantic model subclass of _BasePatchModel:

        class UserPatch(_BasePatchModel):
            __root__: list[registry.union]
            __target_model__ = User
            __registry__ = registry

    This is intended for model-aware patching:
        - You patch Pydantic models.
        - You get Pydantic validation of the result.
        - You use it as a request body type in FastAPI.
    """

    def __class_getitem__(
        cls, param: type[BaseModel] | tuple[type[BaseModel], OperationRegistry]
    ) -> Type[_BasePatchModel]:
        # Provide user-friendly errors that guide proper usage:
        #   JsonPatchFor[User]
        #   JsonPatchFor[(User, registry)]
        if isinstance(param, tuple):
            if len(param) != 2:
                raise TypeError(
                    "JsonPatchFor[(Model, registry)] expects exactly two items"
                )
            model, registry = param
        else:
            model, registry = param, OperationRegistry.standard()

        if not isinstance(model, type) or not issubclass(model, BaseModel):  # type: ignore[redundant-expr]
            raise TypeError(
                f"JsonPatchFor[...] expects a Pydantic BaseModel, got {model!r}"
            )
        if not isinstance(registry, OperationRegistry):
            raise TypeError(
                "JsonPatchFor[(Model, registry)] second argument must be an "
                f"OperationRegistry, got {type(registry).__name__}"
            )

        return cls._create_patch_model(model, registry)

    @staticmethod
    def _create_patch_model(
        model: type[BaseModel],
        registry: OperationRegistry,
    ) -> Type[_BasePatchModel]:
        """Dynamically create the Pydantic model class."""
        op_union: TypeAliasType = registry.union

        PatchModel = create_model(
            f"{model.__name__}Patch",
            __base__=_BasePatchModel,
            __root__=(list[op_union], ...),  # type: ignore[valid-type]
        )

        PatchModel.__target_model__ = model
        PatchModel.__registry__ = registry
        return PatchModel
