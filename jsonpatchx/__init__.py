"""Typed JSON Patch (RFC 6902) utilities powered by Pydantic."""

from jsonpatchx.backend import (
    DEFAULT_POINTER_CLS,
    DEFAULT_SELECTOR_CLS,
)
from jsonpatchx.builtins import (
    AddOp,
    CopyOp,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
from jsonpatchx.exceptions import (
    InvalidJSONPointer,
    InvalidJSONSelector,
    InvalidOperationDefinition,
    InvalidOperationRegistry,
    InvalidPatchResult,
    InvalidPatchTarget,
    PatchConflictError,
    PatchError,
    PatchInternalError,
    TestOpFailed,
)
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.registry import (
    StandardRegistry,
)
from jsonpatchx.schema import OperationSchema
from jsonpatchx.selector import JSONSelector
from jsonpatchx.standard import JsonPatch, apply_patch
from jsonpatchx.types import JSONValue

__all__ = [
    # exceptions
    "InvalidJSONPointer",
    "InvalidJSONSelector",
    "InvalidOperationDefinition",
    "InvalidOperationRegistry",
    "InvalidPatchResult",
    "InvalidPatchTarget",
    "PatchConflictError",
    "PatchError",
    "PatchInternalError",
    "TestOpFailed",
    # types
    "JSONPointer",
    "JSONSelector",
    "JSONValue",
    "DEFAULT_POINTER_CLS",
    "DEFAULT_SELECTOR_CLS",
    # operation specs
    "OperationSchema",
    "StandardRegistry",
    # pydantic helpers
    "JsonPatchFor",
    # built-ins
    "AddOp",
    "RemoveOp",
    "ReplaceOp",
    "MoveOp",
    "CopyOp",
    "TestOp",
    # classics
    "JsonPatch",
    "apply_patch",
]
