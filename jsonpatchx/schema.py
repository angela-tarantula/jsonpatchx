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
from pydantic_core import core_schema as cs

from jsonpatchx.exceptions import (
    InvalidOperationDefinition,
    PatchError,
    PatchInternalError,
)
from jsonpatchx.types import JSONValue, _validate_JSONValue


class OperationSchema(BaseModel, ABC):
    """
    Base class for typed JSON Patch operations.

    Subclass `OperationSchema`, declare `op: Literal["..."]`, and implement `apply` to define a
    typed operation. Instances are Pydantic models: frozen, strict, and validated on parse.

    Example:
        Declare a `replace` operation with a typed path and value:

        ```python
        class ReplaceOp(OperationSchema):
            op: Literal["replace"] = "replace"
            path: JSONPointer[JSONValue]
            value: JSONValue
        ```

        The default value for `op` is optional but recommended. JsonPatchX always
        marks `op` as required in the OpenAPI schema regardless, but a default lets
        Python callers omit it when constructing instances directly.

    Example:
        Support multiple identifiers with `Literal` for schema evolution:

        ```python
        class IncrementOp(OperationSchema):
            op: Literal["increment", "incr"] = "increment"
        ```
        <!-- NOTE: Future: support per-alias deprecation, e.g. mark "incr" deprecated while "increment" stays current.
             Pydantic's Field(deprecated=...) is field-level only — it marks the whole `op` property deprecated in OpenAPI
             and fires at class-definition time, not validation time. What's needed is value-level deprecation:
             emit a DeprecationWarning at validation time when a deprecated alias is used, and surface it in OpenAPI
             via an x-* extension (no standard per-enum-value deprecated key exists in OpenAPI 3.x).
             Note: Field() as a default already works with _get_op_literals — get_type_hints sees the Literal annotation
             cleanly, so the plumbing for op: Literal[...] = Field(...) is already sound. -->

        Multiple identifiers are useful for schema evolution but not recommended for new
        operations. When used, the default value should be the preferred identifier; the
        others act as backwards-compatible aliases.

    Configuration:
        Subclasses inherit all settings below. Override individual keys by declaring
        `model_config = ConfigDict(...)` on the subclass; only the keys you set are
        overridden and the rest are inherited from `OperationSchema`.

        - `frozen=True`: Instances are immutable after construction.
        - `strict=True`: Field values are not coerced. Opt out per field with
          `Field(strict=False)` if a specific field should accept looser input.
        - `extra="allow"`: Extra fields from JSON are preserved. RFC 6902 permits
          extension members; overriding this to `"forbid"` would reject them.
        - `validate_by_alias`, `serialize_by_alias`, `loc_by_alias` are all `True`:
          alias-named fields (such as `from`, aliased to `from_`) are used
          consistently in validation, serialization, and error messages.
        - `validate_return=True`: Validates return values of Pydantic validator
          methods (`@field_validator`, `@model_validator`).

    Notes:
        - Use `model_validator(mode="after")` with `PydanticCustomError` to enforce cross-field
          constraints (for example, rejecting pointer pairs where one is an ancestor of the other).
    """

    model_config = ConfigDict(
        frozen=True,  # Patch operations are not stateful
        strict=True,  # Can be opted out of on a per-field basis if needed, but strict by default for better error quality
        extra="allow",  # Standard JSON Patch allows extras
        validate_by_alias=True,  # Some JSON Patch keys are protected keywords in Python, such as 'from', and require aliases to bypass.
        serialize_by_alias=True,  # Consistent with validation
        loc_by_alias=True,  #  So error messages also use alias. For example, when 'from' is an alias of 'from_', errors should say, "error at: from".
        validate_default=True,  # Validate default values against their intended type annotations
        validate_return=True,  # Validates @field_validator/@model_validator return values; does not affect apply().
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
        Validate the subclass `op` field and cache its identifiers at class-definition time.

        Raises:
            InvalidOperationDefinition: If `op` is missing, not annotated as
                `Literal[str, ...]`, or declared as a `ClassVar` (which Pydantic
                excludes from fields and cannot participate in discriminated-union
                dispatch).
        """
        super().__init_subclass__(**kwargs)
        cls._op_literals = cls._get_op_literals()

    @classmethod
    def _get_op_literals(cls) -> tuple[str, ...]:
        """
        Extract string literal values from the subclass's `op` annotation.

        Supports `op: Literal["add"]` and `op: Literal["add", "create"]`.

        Raises:
            InvalidOperationDefinition: If the subclass does not declare a valid
                `Literal[str, ...]` annotation for `op`.
        """
        try:
            annotations = get_type_hints(cls, include_extras=True)
        except TypeError as e:
            # Py3.12-Py3.13: a bare `Literal` (no args) annotation makes get_type_hints
            # raise TypeError directly instead of returning it as a hint to reject below.
            raise InvalidOperationDefinition(
                f"OperationSchema '{cls.__name__}' is missing valid type hints for required 'op' field. "
                "'op' must be an instance field annotated as a Literal[...] of strings."
            ) from e

        if (
            annotations
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
            The updated JSON document.

        Example:
            ```python
            class IncrementOp(OperationSchema):
                op: Literal["increment"]
                path: JSONPointer[JSONNumber]
                amount: JSONNumber = Field(gt=0)

                def apply(self, doc: JSONValue) -> JSONValue:
                    current = self.path.get(doc)
                    return ReplaceOp(path=self.path, value=current + self.amount).apply(doc)
            ```

        Notes:
            - Implementations may mutate `doc` in place; always return the resulting document.
            - Raise `PatchConflictError` (or a subclass) for expected apply-time failures.
              Input validation errors belong in model validators, not `apply`; unexpected
              exceptions are caught by the patch engine and wrapped as `PatchInternalError`.
            - Whether the caller's original document is mutated depends on the patch engine's
              `inplace` policy, not on this method.
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
    Apply a sequence of operations to a JSON document.

    Arguments:
        ops: Operations to apply, in order.
        doc: JSON document to apply operations to.
        inplace: If `False` (default), `doc` is deep-copied first; the original is not modified.
            If `True`, operations are applied to `doc` directly without that initial copy.

    Returns:
        The patched JSON document.

    Raises:
        PatchError: Expected patch failures raised by operation implementations.
            `index`/`operation` are set to identify the raising operation,
            whether it is a built-in raise site or a custom operation raising
            one of these directly.
        PatchInternalError: Unexpected exceptions wrapped with structured context.

    Notes:
        `inplace=True` is not transactional: if an operation fails mid-patch, earlier
        operations will already have mutated the document with no rollback. Root-targeting
        operations may also return a new object rather than `doc`.
    """
    if not inplace:
        doc = copy.deepcopy(
            doc
        )  # NOTE: consider letting users inject their own copy function

    for index, op in enumerate(ops):
        try:
            doc = op.apply(doc)
            _validate_JSONValue(doc)
        except PatchError as e:
            # Domain-specific patch errors (e.g. TestOpFailed) should propagate
            # unchanged, but identify which operation raised them.
            e.index = index
            e.operation = op
            raise
        except Exception as e:
            raise PatchInternalError(str(e), index=index, operation=op, cause=e) from e

    return doc
