import copy
from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import (
    ClassVar,
    Literal,
    Unpack,
    cast,
    get_args,
    get_origin,
    get_type_hints,  # NOTE: For Py3.14+, this is enhanced for deferred annotations
    override,
)

from pydantic import BaseModel, ConfigDict, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import MISSING
from pydantic_core import core_schema as cs

from jsonpatchx.exceptions import (
    InvalidOperationDefinition,
    PatchError,
    PatchFailureDetail,
    PatchInternalError,
    PatchValidationError,
)
from jsonpatchx.types import JSONValue


class OperationSchema(BaseModel, ABC):
    """
    Base class for typed JSON Patch operations.

    An `OperationSchema` is a Pydantic model representing one JSON Patch operation:
    standard RFC 6902 operations (`add`/`remove`/`replace`/...) and custom domain operations.

    The library's workflow is:

    - Define operations as Pydantic models.
    - Register them in an `OperationRegistry`.
    - Parse incoming patch documents into concrete operation instances via a discriminated union
      keyed by `op`.
    - Apply operations sequentially by calling `apply`.

    Examples:
        Required `op` field:

        class ReplaceOp(OperationSchema):
            op: Literal["replace"] = "replace"
            path: JSONPointer[JSONValue]
            value: JSONValue

        Multiple identifiers (aliases):

        class CreateOp(OperationSchema):
            op: Literal["create", "add"] = "create"

    Notes:
        - `op` must be a normal annotated attribute, not a `ClassVar`. `ClassVar` values are not
          Pydantic fields and cannot participate in discriminated-union dispatch.
        - Instances are frozen and strict by default.
        - Instances are revalidated when parsed, which matters for fields that depend on validation
          context (for example, registry-scoped pointer backends).
        - Subclasses are validated at class-definition time. If `op` is not declared correctly, the
          class raises `InvalidOperationDefinition` during import.
    """

    model_config = ConfigDict(
        frozen=True,  # Patch operations are not stateful
        strict=True,  # Flexible validation can still be provided per field as desired
        extra="allow",  # Standard JSON Patch allows extras
        validate_by_alias=True,  # Some JSON Patch keys are protected keywords in Python, such as 'from', and require aliases to bypass.
        serialize_by_alias=True,  # Consistent with validation
        loc_by_alias=True,  #  So error messages also use alias. For example, when 'from' is an alias of 'from_', errors should say, "error at: from".
        validate_default=True,  # Validate default values against their intended type annotations
        validate_return=True,  # For extra correctness. Also ensures that 'apply()' always results in valid JSON.
        use_enum_values=True,  # For consistent serialization when values are Enums
        allow_inf_nan=False,  # infinite values are not valid JSON
        validation_error_cause=False,  # Consider enabling when Pydantic guarantees a stable error structure. Useful to flip when debugging locally.
    )

    _op_literals: ClassVar[tuple[str, ...]]
    """
    Internal: cached tuple of string op identifiers declared by the subclass' `op: Literal[...]`.

    This is populated during subclass creation and is used by OperationRegistry to build the mapping
    from operation name to schema type.
    """

    @override
    def __init_subclass__(cls, **kwargs: Unpack[ConfigDict]) -> None:
        """
        Hook that validates subclasses at definition time.

        Public subclasses normally do not need to call this directly. The base class ensures that
        every OperationSchema has a properly declared `op` field, and caches the allowed op
        identifiers for registry dispatch.
        """
        super().__init_subclass__(**kwargs)
        cls._op_literals = cls._get_op_literals()

    @classmethod
    def _get_op_literals(cls) -> tuple[str, ...]:
        """
        Internal: extract the string literal values from the subclass' `op` annotation.

        Supported forms:

        - `op: Literal["add"]`
        - `op: Literal["add", "create"]`

        Raises `InvalidOperationDefinition` if the subclass does not declare a valid `Literal[str, ...]`
        annotation for `op`.
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
        Apply this operation to `doc` and return the updated document.

        Arguments:
            doc: Target JSON document.

        Returns:
            The updated document.

        Notes:
            - Implementations may mutate the provided `doc` object in-place and should return the
              updated document (often the same object).
            - Raise `PatchError` subclasses for expected patch failures. Unexpected exceptions will
              be wrapped by the patch engine.
            - Whether the caller-owned document is mutated is controlled by the patch engine
              (see `_apply_ops(..., inplace=...)`), not by this method.
        """

    @classmethod
    @override
    def __get_pydantic_json_schema__(
        cls, schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        json_schema = handler(schema)

        # 'op' is always required, even if it has a runtime default.
        required = set(json_schema.get("required", []))
        json_schema["required"] = sorted(required | {"op"})

        # 'op' is never pre-filled, even if it has a runtime default.
        properties = json_schema.get("properties", {})
        op_schema = cast(dict[str, object], properties.get("op"))
        op_schema.pop("default", None)

        # 'op' gets a consistent description unless specified.
        op_schema.setdefault("description", "The operation to perform.")
        return json_schema


def _apply_ops(
    ops: Sequence[OperationSchema], doc: JSONValue, *, inplace: bool = False
) -> JSONValue:
    """
    Apply a sequence of operations to a JSON document (core patch engine).

    This function is the single source of truth for the library's copy and mutation semantics.

    Arguments:
        ops: Operations to apply, in order.
        doc: Target JSON document.
        inplace: Copy policy. `False` deep-copies `doc` before applying operations.
            `True` applies operations against `doc` without that initial copy.

    Returns:
        The patched document value produced by applying all operations.

    Raises:
        PatchError: Expected patch failures raised by operation implementations.
        PatchInternalError: Unexpected exceptions wrapped with structured context.

    Notes:
        - `inplace=False` (default): the engine deep-copies `doc` first, then applies operations
          to that copy. Operation implementations may mutate the document object they receive. The
          original input object is not modified.
        - `inplace=True`: operations are applied directly to the provided `doc` object. This is faster
          and avoids a deep copy, but it is **not transactional**. If an operation fails mid-patch, earlier
          operations will already have mutated the document (no rollback).
          This is a **copy policy**, not an object-identity guarantee for the returned root value
          (root-targeting operations may rebind the root).
        -  In other words: operations are allowed to be “mutative”, and the engine decides whether those
           mutations hit the original input or a deep-copied working document.
    """
    if not inplace:
        doc = copy.deepcopy(
            doc
        )  # NOTE: consider letting users inject their own copy function

    for index, op in enumerate(ops):
        try:
            doc = op.apply(doc)
        except PatchError:
            # Domain-specific patch errors (e.g. TestOpFailed) should propagate unchanged.
            raise
        except Exception as e:
            detail = PatchFailureDetail(
                index=index,
                op=op,
                message=str(e),
                cause_type=type(e).__name__,
            )
            raise PatchInternalError(detail, cause=e) from e

    if doc is MISSING:  # type: ignore[comparison-overlap]
        raise PatchValidationError(
            "The patch deleted the document, which is not allowed."
        )
    return doc
