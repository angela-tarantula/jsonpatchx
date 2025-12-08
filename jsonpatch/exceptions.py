class PatchError(Exception):
    """Base class for JSON patch exceptions."""


class InvalidOperationSchema(PatchError):
    """An OperationSchema is invalid."""


class InvalidOperationRegistry(PatchError):
    """A OperationRegistry has incompatible OperationSchemas."""


class PatchApplicationError(PatchError):
    """A JSON Patch failed."""


class TestOpFailed(PatchApplicationError):
    """A test operation failed"""
