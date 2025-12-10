from typing import ClassVar, Type, TypeVar

from pydantic import BaseModel, ConfigDict

from jsonpatch.exceptions import InvalidJsonPatch
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.standard import _apply_ops

ModelT = TypeVar("ModelT", bound=BaseModel)


class _BasePatchModel(BaseModel):
    """
    Base class for all dynamically-created JsonPatchFor[...] models.

    Each subclass is expected to have:

    - __root__: list[OperationSchema] (actually registry.union)
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
