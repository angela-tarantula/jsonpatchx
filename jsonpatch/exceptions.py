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


class TestOpFailed(PatchApplicationError):
    """A test operation failed."""
