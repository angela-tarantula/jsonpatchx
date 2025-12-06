class PatchError(Exception):
    """Base class for JSON patch exceptions."""


class InvalidOperationSchema(PatchError):
    """An OperationSchema is invalid."""


class InvalidPatchSchema(PatchError):
    """A PatchSchema has incompatible OperationSchemas."""


class PatchApplicationError(PatchError):
    """A JSON Patch failed."""


class TestOpFailed(PatchApplicationError):
    """A test operation failed"""
