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

    An ``OperationSchema`` is a Pydantic model representing one JSON Patch operation:
    standard RFC 6902 operations (``add``/``remove``/``replace``/...) and custom domain operations.

    The library's workflow is:

    - Define operations as Pydantic models.
    - Register them in an :class:`~jsonpatch.registry.OperationRegistry`.
    - Parse incoming patch documents into concrete operation instances via a discriminated union
      keyed by ``op``.
    - Apply operations sequentially by calling :meth:`apply`.

    ### Required fields

    Subclasses must define an ``op`` *model field* annotated as ``Literal[...]`` of one or more strings:

    .. code-block:: python

        class ReplaceOp(OperationSchema):
            op: Literal["replace"] = "replace"
            path: JSONPointer[JSONValue]
            value: JSONValue

    Multiple identifiers are allowed (aliases):

    .. code-block:: python

        class CreateOp(OperationSchema):
            op: Literal["create", "add"] = "create"

    Note: ``op`` must be a normal annotated attribute, **not** a ``ClassVar``. ``ClassVar`` values
    are not Pydantic fields and cannot participate in discriminated-union dispatch.

    ### Immutability and strictness

    ``OperationSchema`` instances are frozen and strict by default.
    Instances are revalidated when parsed (important when fields depend on validation context,
    such as registry-scoped pointer backends).

    ### Subclass validation

    Subclasses are validated at class-definition time. If ``op`` is not declared correctly, the
    class raises :class:`~jsonpatch.exceptions.InvalidOperationSchema` early (during import).
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
        Apply this operation to a JSON document and return the updated document.

        ### Mutation contract

        Implementations **may mutate** the provided ``doc`` in-place and must return the updated
        document (which may be the same object). Whether this results in mutation of the *original*
        caller-owned document is controlled by the patch engine (e.g., engines often deep-copy the
        input first when ``inplace=False``).

        ### Errors

        On failure, raise library patch exceptions (for example
        :class:`~jsonpatch.exceptions.PatchApplicationError` or a more specific subclass) so callers can
        treat patch failures as request/data errors rather than unexpected crashes.
        """
        ...
