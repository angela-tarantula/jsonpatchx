from abc import ABC, abstractmethod
from typing import (
    Annotated,
    ClassVar,
    Literal,
    Unpack,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    override,
)

from pydantic import BaseModel, ConfigDict

from jsonpatch.exceptions import InvalidOperationSchema
from jsonpatch.types import JSONValue


class OperationSchema(BaseModel, ABC):
    """
    Base class for declarative JSON Patch operation schemas,
    represented as strongly-typed Pydantic models.

    Ensures the 'op' is annotated as a Literal of strings.
    """

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        revalidate_instances="always",  # necessary for converting custom PointerBackends
    )

    _op_literals: ClassVar[tuple[str, ...]]

    @override
    def __init_subclass__(cls, **kwargs: Unpack[ConfigDict]) -> None:
        """Validate the operation schema."""
        super().__init_subclass__(**kwargs)

        if not (literals := cls._extract_op_literals()):
            raise InvalidOperationSchema(
                f"OperationSchema '{cls.__name__}'.op must be annotated as Literal of string(s)."
            )
        cls._op_literals = literals

    @classmethod
    def _extract_op_literals(cls) -> tuple[str, ...]:
        """
        Extract the string literal values declared for the 'op' field.

        Supports:
            op: Literal["add"]
            op: Literal["add", "create"]
            op: Annotated[Literal["add"], SomeMetadata]
        """
        hints = get_type_hints(cls, include_extras=True)
        op_anno = hints.get("op")
        if op_anno is None:
            return ()

        origin = get_origin(op_anno)

        # Strip Annotated[...] if present
        if origin is Annotated:
            inner_anno, *_ = get_args(op_anno)
            op_anno = inner_anno
            origin = get_origin(op_anno)

        if origin is not Literal:
            return ()

        literal_vals = get_args(op_anno)
        if not literal_vals or not all(isinstance(v, str) for v in literal_vals):
            return ()

        return cast(tuple[str, ...], literal_vals)

    @abstractmethod
    def apply(self, doc: JSONValue) -> JSONValue:
        """Apply this operation to a JSON document."""
        ...
