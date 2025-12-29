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
    Base class for **typed JSON Patch operations**.

    An ``OperationSchema`` is a Pydantic model that represents one JSON Patch operation
    (standard RFC 6902 operations like ``add``/``remove``/``replace`` as well as custom,
    domain-specific operations).

    This class is designed to support the library's primary workflow:

    - You define operations as strongly typed Pydantic models.
    - An :class:`~jsonpatch.registry.OperationRegistry` collects those operation types and builds a
      discriminated union keyed by the ``op`` field.
    - Pydantic then parses incoming patch documents into concrete operation objects.
    - The patch engine applies operations by calling :meth:`apply`.

    ### Required fields

    Subclasses must define an ``op`` field annotated as ``Literal[...]`` of one or more strings:

    .. code-block:: python

        class ReplaceOp(OperationSchema):
            op: Literal["replace"] = "replace"
            path: JSONPointer[JSONValue]
            value: JSONValue

    Multiple identifiers are allowed (aliases):

    .. code-block:: python

        class CreateOp(OperationSchema):
            op: Literal["create", "add"] = "create"

    ### Immutability and strictness

    ``OperationSchema`` instances are:

    - **frozen**: operations are immutable once constructed
    - **strict**: Pydantic will not coerce types
    - **revalidated**: instances are revalidated when parsed, which is important when operations
      include custom JSONPointer backends that depend on validation context.

    ### Subclass validation

    At class-definition time, this base class validates that ``op`` is declared correctly.
    If not, it raises :class:`~jsonpatch.exceptions.InvalidOperationSchema` early, so mistakes are
    caught during import rather than at runtime.

    The ``op`` attribute must be a *Pydantic field* (i.e., a normal annotated attribute), not a ``ClassVar``;
    ``ClassVar`` values are not model fields and cannot participate in discriminated-union dispatch.
    """

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        revalidate_instances="always",  # necessary for converting custom PointerBackends
    )

    _op_literals: ClassVar[tuple[str, ...]]
    """
    Internal: cached tuple of string op identifiers declared by the subclass' ``op: Literal[...]``.

    This is populated during subclass creation and is used by OperationRegistry to build the mapping
    from operation name to schema type.
    """

    @override
    def __init_subclass__(cls, **kwargs: Unpack[ConfigDict]) -> None:
        """
        Hook that validates subclasses at definition time.

        Public subclasses normally do not need to call this directly. The base class ensures that
        every OperationSchema has a properly declared ``op`` field, and caches the allowed op
        identifiers for registry dispatch.
        """
        super().__init_subclass__(**kwargs)

        if not (literals := cls._extract_op_literals()):
            raise InvalidOperationSchema(
                f"OperationSchema '{cls.__name__}'.op must be annotated as Literal of string(s). "
                "op must be declared as a model field (not ClassVar)."
            )
        cls._op_literals = literals

    @classmethod
    def _extract_op_literals(cls) -> tuple[str, ...]:
        """
        Internal: extract the string literal values from the subclass' ``op`` annotation.

        Supported forms:

        - ``op: Literal["add"]``
        - ``op: Literal["add", "create"]``
        - ``op: Annotated[Literal["add"], ...]``

        Returns an empty tuple if the subclass does not declare a valid ``Literal[str, ...]``
        annotation for ``op``.
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
        """
        Apply this operation to a JSON document.

        Subclasses implement the semantic behavior of the operation. The patch engine calls this
        method sequentially for each operation in a patch document.

        ### Contract

        - ``doc`` is a JSON value (dict/list/primitives) as defined by :data:`~jsonpatch.types.JSONValue`.
        - Implementations **may mutate** the provided ``doc`` in-place and must return the updated document
          (which may be the same object). Whether callers observe in-place mutation is controlled by the
          patch engine (e.g., higher-level helpers may deep-copy the document before applying operations).
        - On failure, implementations should raise the library's patch exceptions
          (e.g., :class:`~jsonpatch.exceptions.PatchApplicationError` or more specific subclasses)
          so callers can distinguish “invalid patch” from unexpected errors.

        Returns the patched JSON document.
        """
        ...
