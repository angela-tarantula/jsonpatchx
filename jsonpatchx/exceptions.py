from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from jsonpatchx.schema import OperationSchema

# Exception hierarchy and HTTP error mapping:
#
# PatchError
# ├── InvalidPatchResult             422 — patch applied, result fails validation
# │                                        (output invalid)
# ├── PatchConflictError             409 — patch valid, document state rejects it
# │   └── TestOpFailed               409 — RFC 6902 test op value mismatch
# └── PatchInternalError             500 — unexpected exception during apply
#
# Every PatchError carries `index`/`operation`, identifying which operation in
# the patch document is implicated, when there is one. `_apply_ops` attaches
# both to any PatchError raised from inside an operation's own apply(),
# whether a built-in raise site or a custom operation; neither is settable at
# construction time, since any caller-supplied value would just be overwritten
# by `_apply_ops` anyway. They stay `None` when a failure is not attributable
# to one operation (for example, InvalidPatchResult raised from the final
# whole-document re-validation after every operation already applied without
# conflict).
#
# Non-PatchError exceptions that may surface:
#   InvalidOperationDefinition(TypeError)  Raised from __init_subclass__ at
#   InvalidOperationRegistry(TypeError)    class-definition time or registry-
#                                          construction time (developer/config
#                                          errors), never during op.apply(), so
#                                          they never reach a running request.
#   InvalidPatchTarget(TypeError)   A supplied patch target/document is not
#                                    valid: wrong model instance, or a
#                                    document/model that isn't representable
#                                    as JSON. Argument validation on the call
#                                    that applies the patch, not a
#                                    patch-domain failure, so it is not a
#                                    PatchError. install_jsonpatch_error_
#                                    handlers registers a dedicated handler
#                                    for it (500) alongside the PatchError
#                                    handler.
#   InvalidJSONPointer(ValueError)   Raised inside Pydantic field validation
#   InvalidJSONSelector(ValueError)  (parsing a real patch document), pydantic
#                                    wraps it in ValidationError (422) automatically
#                                    because it is a ValueError. Raised during
#                                    op.apply(), _apply_ops wraps it as
#                                    PatchInternalError (500), same as any other
#                                    unexpected exception. Raised anywhere else
#                                    uncaught (e.g. calling .parse() directly), it
#                                    is an ordinary unhandled ValueError (500).
#   ValidationError (Pydantic)       422 — FastAPI's own handler catches this
#   TypeError                        500 — backend implementation bug (wrong type
#                                         returned or incompatible backends mixed);
#                                         _apply_ops wraps it as PatchInternalError


class PatchError(Exception):
    """
    Base class for application-time JSON Patch errors.

    This type is not raised directly; it anchors the error hierarchy for tooling
    and API error mapping.

    Attributes:
        error_type: Stable, machine-readable identifier for this error kind,
            independent of the Python class name.
        index: 0-based index of the implicated operation in the patch
            document, or `None` if this failure is not attributable to a
            single operation. Not provided by callers; JsonPatchX sets it
            once the failure is attributed to an operation.
        operation: The implicated operation, or `None` under the same
            condition as `index`. Not provided by callers; set under the
            same condition as `index`.
    """

    error_type: ClassVar[str] = "patch_error"

    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.index: int | None = None
        self.operation: OperationSchema | None = None


class InvalidPatchResult(PatchError):
    """
    Applying a patch produced a result that fails validation.

    Every operation applied without conflict, but the resulting document is
    unacceptable (for example, it violates the target model's schema). Custom
    operations may also raise this directly to signal that an
    otherwise-successful application produced an invalid result; in that case
    `index`/`operation` identify the raising operation, unlike the
    whole-document re-validation case, where they are `None`.

    Attributes:
        errors: Structured validation errors (in the shape of
            `pydantic.ValidationError.errors()`) when this was raised from a
            wrapped `ValidationError`, or `None` when raised directly with no
            underlying validation error.

    Examples:
        - Model-aware patching produces a document that violates the target model.

    Typical HTTP mapping:
        422 Unprocessable Entity.
    """

    error_type: ClassVar[str] = "invalid_patch_result"

    def __init__(
        self,
        *args: object,
        errors: Sequence[Mapping[str, Any]] | None = None,
    ) -> None:
        super().__init__(*args)
        self.errors = errors


class PatchConflictError(PatchError):
    """
    A JSON Patch failed due to a conflict with the current document state.

    Custom operations may also raise this directly to signal that the
    current document state does not satisfy a precondition the operation
    depends on.

    Examples:
        - Path does not exist or array index is out of range.
        - Removing a value at a missing or invalid path.

    Typical HTTP mapping:
        409 Conflict (some APIs may prefer 422).
    """

    error_type: ClassVar[str] = "patch_conflict"


class TestOpFailed(PatchConflictError):
    """
    A test operation failed (RFC 6902).

    Custom operations that implement test-like, assert-a-value-then-continue
    semantics may also raise this directly.

    Typical HTTP mapping:
        409 Conflict (state mismatch).
    """

    error_type: ClassVar[str] = "test_op_failed"

    __test__ = False


class PatchInternalError(PatchError):
    """
    Unexpected exception during patch execution wrapped with structured context.

    This is meant for API layers and debuggability: it always identifies the
    exact operation index and payload, and preserves the original exception
    as `__cause__`.

    Attributes:
        cause_type: The exception class name of the underlying cause.

    Examples:
        A ZeroDivisionError raised inside a custom op implementation that fails
        to catch it.

    Typical HTTP mapping:
        500 Internal Server Error (unexpected failure).
    """

    error_type: ClassVar[str] = "patch_internal_error"

    def __init__(
        self,
        message: str,
        *,
        index: int,
        operation: OperationSchema,
        cause: BaseException,
    ) -> None:
        op_name = getattr(operation, "op")
        formatted = f"Error applying op[{index}] ({op_name}): {message}"
        super().__init__(formatted)
        self.index = index
        self.operation = operation
        self.__cause__ = cause

    @property
    def cause_type(self) -> str:
        """The exception class name of the underlying cause."""
        return type(self.__cause__).__name__


class InvalidOperationDefinition(TypeError):
    """
    An OperationSchema definition is invalid (developer error).

    Examples:
        - `op` is missing or not declared as `Literal[...]`.
        - `op` is declared as a ClassVar, so it is not a model field.
    """


class InvalidOperationRegistry(TypeError):
    """
    An OperationRegistry has incompatible OperationSchemas (developer error).

    Examples:
        - Duplicate `op` identifiers across schemas.
        - Non-OperationSchema classes provided to the registry.
    """


class InvalidPatchTarget(TypeError):
    """
    The value supplied as a patch target or document is not valid.

    This is argument validation on the call that applies the patch, not
    something a patch document's content can trigger: the caller supplied a
    value that cannot serve as a patch target or document.

    Attributes:
        error_type: Stable, machine-readable identifier for this error kind.

    Examples:
        - The document is not a valid JSON value (for example, a `datetime` or
          a custom object).
        - For model-aware patching, the target is not an instance of the
          model the patch was bound to, even if it is otherwise a valid,
          well-formed object.
        - For model-aware patching, the target model's own `model_dump()`
          produces non-JSON data.

    Typical HTTP mapping:
        500 Internal Server Error.
    """

    error_type: ClassVar[str] = "invalid_patch_target"


class InvalidJSONPointer(ValueError):
    """
    A JSON Pointer definition or instance is invalid.

    A custom pointer backend's own exception for an unparsable string is
    normalized into this exception automatically; the original exception is
    available as `__cause__`.

    Examples:
        - Pointer string is malformed or uses an incompatible backend.
        - Pointer backend class fails protocol checks.

    Typical HTTP mapping:
        422 Unprocessable Entity when raised during Pydantic field
        validation of a patch document; a plain unhandled `ValueError`
        (500 by default) anywhere else.
    """


class InvalidJSONSelector(ValueError):
    """
    A JSON selector definition or instance is invalid.

    A custom selector backend's own exception for an unparsable string is
    normalized into this exception automatically; the original exception is
    available as `__cause__`.

    Examples:
        - Selector string is malformed or uses an incompatible backend.
        - Selector backend class fails protocol checks.

    Typical HTTP mapping:
        422 Unprocessable Entity when raised during Pydantic field
        validation of a patch document; a plain unhandled `ValueError`
        (500 by default) anywhere else.
    """
