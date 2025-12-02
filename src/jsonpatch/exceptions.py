from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from jsonpatch.models import Operation, PatchOperation


class JsonPatchException(Exception):
    """Base for all json-patch errors."""

    pass


class InvalidJsonPatch(JsonPatchException):
    """Base for json-patch errors where a JSON Patch is intrinsically invalid."""

    pass


class JsonPatchConflict(JsonPatchException):
    """Base for json-patch errors where a JSON Patch is incompatible with the target document."""

    pass


class MissingMember(InvalidJsonPatch):
    """A required member of a JSON Patch operation is missing."""

    def __init__(self, operation: Operation, member: str) -> None:
        super().__init__(
            f"Missing required member '{member}' in operation '{operation._identifier}'"
        )
        self.operation = operation
        self.member = member


class UnrecognizedPatchOperation(InvalidJsonPatch):
    """A JSON Patch operation has an unrecognized name."""

    def __init__(self, patch_operation: PatchOperation) -> None:
        super().__init__(f"Unrecognized patch operation '{patch_operation.name}'")
        self.operation = patch_operation


class MemberTypeMismatch(InvalidJsonPatch):
    """A member in a JSON Patch operation has an invalid type."""

    def __init__(self, operation: Operation, member: str) -> None:
        value = operation.get(member)
        unexpected_type = type(value)
        unexpected_type_name = getattr(
            unexpected_type, "__name__", str(unexpected_type)
        )
        super().__init__(
            f"Unexpected type '{unexpected_type_name}' for member '{member}' "
            f"in operation '{operation._identifier}'. Value was: {value!r}"
        )
        self.operation = operation
        self.member = member


class MemberValueMismatch(InvalidJsonPatch):
    """A member in a JSON Patch operation has an invalid value."""

    def __init__(self, operation: Operation, member: str, details: str) -> None:
        super().__init__(
            f"Invalid value for member '{member}' in operation '{operation._identifier}': {details}"
        )
        self.operation = operation
        self.member = member
        self.details = details


class TestOperationFailed(JsonPatchException):
    """A JSON Patch test operation failed."""

    pass
