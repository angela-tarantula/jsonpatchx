from collections.abc import MutableMapping
from typing import Literal, overload


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

    @overload
    def __init__(self, operation: MutableMapping, member: Literal["op"]) -> None: ...

    @overload
    def __init__(self, operation: str, member: str) -> None: ...

    def __init__(self, operation: str | MutableMapping, member: str):
        super().__init__(f"Missing required {member=} in {operation=}")
        self.operation = operation
        self.member = member


class UnrecognizedOperation(InvalidJsonPatch):
    """A JSON Patch operation is invalid."""

    def __init__(self, operation: str):
        super().__init__(f"Unrecognized {operation=}")
        self.operation = operation


class MemberTypeMismatch(InvalidJsonPatch):
    """A member in a JSON Patch operation has an invalid type."""

    def __init__(self, operation: str, member: str, expected_type: type):
        expected_type_name = getattr(expected_type, "__name__", str(expected_type))
        super().__init__(
            f"Expected type {expected_type_name} for {member=} in {operation=}."
        )
        self.operation = operation
        self.member = member
        self.expected_type = expected_type


class MemberValueMismatch(InvalidJsonPatch):
    """A member in a JSON Patch operation has an invalid value."""

    def __init__(self, operation: str, member: str, details: str):
        super().__init__(f"Invalid value for {member=} in {operation=}: {details}")
        self.operation = operation
        self.member = member
        self.details = details


class JsonPatchTestFailed(JsonPatchException):
    """Exception raised when a test operation in JSON Patch fails."""

    pass
