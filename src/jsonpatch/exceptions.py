from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jsonpatch.models import Operation


class JsonPatchException(Exception):
    """Base for all json-patch errors."""

    pass


class InvalidJsonPatch(JsonPatchException):
    """A JSON Patch is intrinsically invalid."""

    pass


class JsonPatchConflict(JsonPatchException):
    """A JSON Patch is incompatible with the target document."""

    pass


class MissingMember(InvalidJsonPatch):
    """A required member of a JSON Patch operation is missing."""

    def __init__(self, operation: Operation, member: str) -> None:
        super().__init__(f"Missing required {member=} in {operation.name=}")
        self.operation = operation
        self.member = member


class UnrecognizedOperation(InvalidJsonPatch):
    """A JSON Patch operation is invalid."""

    def __init__(self, operation: Operation) -> None:
        super().__init__(f"Unrecognized {operation.name=}")
        self.operation = operation


class MemberTypeMismatch(InvalidJsonPatch):
    """A member in a JSON Patch operation has an invalid type."""

    def __init__(self, operation: Operation, member: str) -> None:
        unexpected_type = type(operation[member])
        unexpected_type_name = getattr(
            unexpected_type, "__name__", str(unexpected_type)
        )
        super().__init__(
            f"Unexpected type {unexpected_type_name} for {member=} in {operation.name=}."
        )
        self.operation = operation
        self.member = member


class MemberValueMismatch(InvalidJsonPatch):
    """A member in a JSON Patch operation has an invalid value."""

    def __init__(self, operation: Operation, member: str, details: str) -> None:
        super().__init__(f"Invalid value for {member=} in {operation.name=}: {details}")
        self.operation = operation
        self.member = member
        self.details = details


class JsonPatchTestFailed(JsonPatchException):
    """Exception raised when a test operation in JSON Patch fails."""

    pass
