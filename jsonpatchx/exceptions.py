from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jsonpatchx.schema import OperationSchema


class PatchError(Exception):
    """Base class for JSON Patch errors."""


class InvalidOperationSchema(PatchError):
    """An OperationSchema definition or instance is invalid."""


class InvalidJSONPointer(PatchError):
    """A JSON Pointer definition or instance is invalid."""


class InvalidOperationRegistry(PatchError):
    """An OperationRegistry has incompatible OperationSchemas."""


class InvalidJsonPatch(PatchError):
    """A JsonPatch document is invalid or malformed."""


class PatchApplicationError(PatchError):
    """A JSON Patch failed during application."""


class PatchValidationError(PatchApplicationError):
    """Patched data failed validation against a target schema."""


class TestOpFailed(PatchApplicationError):
    """A test operation failed."""


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


class PatchExecutionError(PatchApplicationError):
    """
    Unexpected exception during patch execution wrapped with structured context.

    This is meant for API layers and debuggability:
    - It points at the exact op index
    - It includes the full op payload (best-effort JSON shape)

    Example: Providing context for a ZeroDivisionError during patch application.
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
