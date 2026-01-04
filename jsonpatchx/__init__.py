"""Typed JSON Patch (RFC 6902) utilities powered by Pydantic."""

from jsonpatchx.builtins import (
    STANDARD_OPS,
    AddOp,
    CopyOp,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
from jsonpatchx.exceptions import (
    InvalidJSONPointer,
    InvalidOperationRegistry,
    InvalidOperationSchema,
    PatchConflictError,
    PatchError,
    PatchFailureDetail,
    PatchInternalError,
    PatchValidationError,
    TestOpFailed,
)
from jsonpatchx.pydantic import JsonPatchFor, patch_body_for_json, patch_body_for_model
from jsonpatchx.registry import OperationRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch, apply_patch
from jsonpatchx.types import JSONPointer, JSONValue

__all__ = [
    # exceptions
    "InvalidJSONPointer",
    "InvalidOperationSchema",
    "InvalidOperationRegistry",
    "PatchConflictError",
    "PatchError",
    "PatchInternalError",
    "PatchFailureDetail",
    "PatchValidationError",
    "TestOpFailed",
    # types
    "JSONPointer",
    "JSONValue",
    # operation specs
    "OperationSchema",
    "OperationRegistry",
    # pydantic helpers
    "JsonPatchFor",
    "patch_body_for_json",
    "patch_body_for_model",
    # built-ins
    "STANDARD_OPS",
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
