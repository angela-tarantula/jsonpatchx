from abc import ABC, abstractmethod
from typing import (
    ClassVar,
    Literal,
    Unpack,
    get_args,
    get_origin,
    get_type_hints,  # NOTE: For Py3.14+, this is enhanced for deferred annotations
    override,
)

from pydantic import BaseModel, ConfigDict, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema as cs

from jsonpatchx.exceptions import InvalidOperationDefinition
from jsonpatchx.types import JSONValue


class OperationSchema(BaseModel, ABC):
    """
    Base class for typed JSON Patch operations.

    An ``OperationSchema`` is a Pydantic model representing one JSON Patch operation:
    standard RFC 6902 operations (``add``/``remove``/``replace``/...) and custom domain operations.

    The library's workflow is:

    - Define operations as Pydantic models.
    - Register them in an ``OperationRegistry``.
    - Parse incoming patch documents into concrete operation instances via a discriminated union
      keyed by ``op``.
    - Apply operations sequentially by calling ``apply``.

    Example:
        Required ``op`` field:

        ``class ReplaceOp(OperationSchema):``
        ``    op: Literal["replace"] = "replace"``
        ``    path: JSONPointer[JSONValue]``
        ``    value: JSONValue``

        Multiple identifiers (aliases):

        ``class CreateOp(OperationSchema):``
        ``    op: Literal["create", "add"] = "create"``

    Notes:
        - ``op`` must be a normal annotated attribute, not a ``ClassVar``. ``ClassVar`` values are not
          Pydantic fields and cannot participate in discriminated-union dispatch.
        - Instances are frozen and strict by default.
        - Instances are revalidated when parsed, which matters for fields that depend on validation
          context (for example, registry-scoped pointer backends).
        - Subclasses are validated at class-definition time. If ``op`` is not declared correctly, the
          class raises ``InvalidOperationDefinition`` during import.
    """

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="allow",
        revalidate_instances="always",  # necessary for converting custom PointerBackends
        # NOTE: validators may run multiple times; guide users to write idempotent validators.
        populate_by_name=True,  # Allow Python-side construction with field names (e.g., from_), while JSON parsing stays alias-only via by_name=False in registries
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
        cls._op_literals = cls._get_op_literals()

    @classmethod
    def _get_op_literals(cls) -> tuple[str, ...]:
        """
        Internal: extract the string literal values from the subclass' ``op`` annotation.

        Supported forms:

        - ``op: Literal["add"]``
        - ``op: Literal["add", "create"]``

        Raises ``InvalidOperationDefinition`` if the subclass does not declare a valid ``Literal[str, ...]``
        annotation for ``op``.
        """
        if (
            (annotations := get_type_hints(cls, include_extras=True))
            and (op_annotation := annotations.get("op"))
            and (get_origin(op_annotation) is Literal)
            and (op_literals := get_args(op_annotation))
            and all(isinstance(v, str) for v in op_literals)
        ):
            return op_literals
        else:
            raise InvalidOperationDefinition(
                f"OperationSchema '{cls.__name__}' is missing valid type hints for required 'op' field. "
                "'op' must be an instance field annotated as a Literal[...] of strings."
            )

    @abstractmethod
    def apply(self, doc: JSONValue) -> JSONValue:
        """
        Apply this operation to ``doc`` and return the updated document.

        Notes:
            - Implementations may mutate the provided ``doc`` object in-place and should return the
              updated document (often the same object).
            - Raise ``PatchError`` subclasses for expected patch failures. Unexpected exceptions will
              be wrapped by the patch engine.
            - Whether the caller-owned document is mutated is controlled by the patch engine
              (see ``_apply_ops(..., inplace=...)``), not by this method.
        """

    @classmethod
    @override
    def __get_pydantic_json_schema__(
        cls, schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(schema)
        # 1. allow users to set "op" defaults, but tell OpenAPI it's required
        # 2. tell OpenAPI that additionalProperties are forbidden
        assert json_schema["type"] == "object", "internal error"
        required = set(json_schema.get("required", []))
        required.add("op")
        json_schema["required"] = sorted(required)
        json_schema.setdefault("additionalProperties", True)
        json_schema["properties"]["op"].setdefault(
            "description", "The operation to perform."
        )
        return json_schema
