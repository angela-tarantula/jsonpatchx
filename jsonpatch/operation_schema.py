from abc import ABC, abstractmethod
from typing import (
    ClassVar,
    Literal,
    Unpack,
    cast,
    get_args,
    get_origin,
    override,
)

from pydantic import BaseModel, ConfigDict

from jsonpatch.exceptions import InvalidOperationSchema
from jsonpatch.types import JsonValueType


class OperationSchema(BaseModel, ABC):
    """
    The base class for declarative JSON Patch operation schemas,
    represented as strongly-typed Pydantic models.
    """

    model_config = ConfigDict(frozen=True)
    _op_literals: ClassVar[tuple[str]]

    @override
    def __init_subclass__(cls, **kwargs: Unpack[ConfigDict]) -> None:
        """Validate the operation schema."""
        super().__init_subclass__(**kwargs)
        if not cls._is_annotated_correctly():
            raise InvalidOperationSchema(
                f"OperationSchema '{cls.__name__}'.op must be annotated as Literal[str, ...]"
            )
        cls._op_literals = get_args(cls.__annotations__["op"])

    @classmethod
    def _is_annotated_correctly(cls) -> bool:
        """Confirms 'op' field is annotated as Literal[str, ...]"""
        return bool(
            (op_anno := cls.__annotations__.get("op"))  # op is annotated
            and (cast(object, get_origin(op_anno)) is Literal)  # op is Literal
            and bool(literal_vals := get_args(op_anno))  # op is Literal[...]
            and all(isinstance(v, str) for v in literal_vals)  # op is Literal[str, ...]
        )

    @abstractmethod
    def apply(self, doc: JsonValueType) -> JsonValueType:
        """Apply this operation to a JSON document."""
        ...
