class PatchError(Exception):
    """Base class for JSON patch exceptions."""


class InvalidOperationSchema(PatchError):
    """An OperationSchema is invalid."""


class OperationValidationError(PatchError):
    """An OperationSchema instance was invalid."""


class InvalidOperationRegistry(PatchError):
    """A OperationRegistry has incompatible OperationSchemas."""


class InvalidJsonPatch(PatchError):
    """A JsonPatch is invalid."""


class PatchApplicationError(PatchError):
    """A JSON Patch failed."""


class TestOpFailed(PatchApplicationError):
    """A test operation failed"""
