from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jsonpatchx.schema import OperationSchema

# Exception hierarchy and HTTP error mapping:
#
# PatchError
# ├── InvalidPatchTarget             500 — non-JSON doc passed to patch engine,
# │                                        or wrong model instance
# ├── PatchConflictError             409 — patch valid, document state rejects it
# │   └── TestOpFailed               409 — RFC 6902 test op value mismatch
# ├── PatchValidationError           422 — patch applied, result fails model schema
# └── PatchInternalError             500 — unexpected exception during apply
#
# Non-PatchError exceptions that may surface:
#   InvalidOperationDefinition(TypeError)  Raised from __init_subclass__ at
#   InvalidOperationRegistry(TypeError)    class-definition time or registry-
#                                          construction time (developer/config
#                                          errors), never during op.apply(), so
#                                          they never reach a running request.
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


class InvalidJSONPointer(ValueError):
    """
    A JSON Pointer definition or instance is invalid.

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

    Examples:
        - Selector string is malformed or uses an incompatible backend.
        - Selector backend class fails protocol checks.

    Typical HTTP mapping:
        422 Unprocessable Entity when raised during Pydantic field
        validation of a patch document; a plain unhandled `ValueError`
        (500 by default) anywhere else.
    """


class PatchError(Exception):
    """
    Base class for application-time JSON Patch errors.

    This type is not raised directly; it anchors the error hierarchy for tooling
    and API error mapping.
    """


class PatchConflictError(PatchError):
    """
    A JSON Patch failed due to a conflict with the current document state.

    Examples:
        - Path does not exist or array index is out of range.
        - Removing a value at a missing or invalid path.

    Typical HTTP mapping:
        409 Conflict (some APIs may prefer 422).
    """


class PatchValidationError(PatchError):
    """
    Patched data failed validation against the target model schema.

    Examples:
        - Model-aware patching produces a document that violates the target model.

    Typical HTTP mapping:
        422 Unprocessable Entity.
    """


class InvalidPatchTarget(PatchError):
    """
    The document passed to the patch engine is not a valid JSON value (server error).

    This is a programmer or configuration error: the caller supplied a value that
    cannot be a JSON document (for example, a `datetime` or a custom object).

    Typical HTTP mapping:
        500 Internal Server Error.
    """


class TestOpFailed(PatchConflictError):
    """
    A test operation failed (RFC 6902).

    Typical HTTP mapping:
        409 Conflict (state mismatch).
    """

    __test__ = False


@dataclass(frozen=True, slots=True)
class PatchFailureDetail:
    """
    Structured failure details for patch application.

    Attributes:
        index: 0-based index of the operation within the patch document.
        op: Best-effort JSON-serializable representation of the failing operation.
            For OperationSchema instances, this is model_dump(mode="json", by_alias=True).
            For mapping-like inputs, this is dict(op).
            As a last resort, {"repr": repr(op)}.
        message: Human-readable error message.
        cause_type: The exception class name of the underlying cause (useful for logging / API error mapping).
    """

    index: int
    op: OperationSchema
    message: str
    cause_type: str | None = None


class PatchInternalError(PatchError):
    """
    Unexpected exception during patch execution wrapped with structured context.

    This is meant for API layers and debuggability:
        - points at the exact op index
        - includes the full op payload (best-effort JSON shape)

    Examples:
        A ZeroDivisionError raised inside a custom op implementation that fails
        to catch it.

    Typical HTTP mapping:
        500 Internal Server Error (unexpected failure).
    """

    def __init__(
        self, detail: PatchFailureDetail, *, cause: BaseException | None = None
    ):
        self.detail = detail
        super().__init__(self._format(detail))
        if cause is not None:
            self.__cause__ = cause

    @staticmethod
    def _format(d: PatchFailureDetail) -> str:
        op_name = getattr(d.op, "op")
        return f"Error applying op[{d.index}] ({op_name}): {d.message}"
