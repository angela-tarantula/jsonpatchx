"""Typed JSON Patch (RFC 6902) utilities powered by Pydantic."""

from jsonpatch.builtins import (
    STANDARD_OPS,
    AddOp,
    CopyOp,
    MoveOp,
    RemoveOp,
    ReplaceOp,
    TestOp,
)
from jsonpatch.exceptions import (
    InvalidJsonPatch,
    InvalidJSONPointer,
    InvalidOperationRegistry,
    InvalidOperationSchema,
    PatchApplicationError,
    PatchError,
    PatchExecutionError,
    PatchFailureDetail,
    TestOpFailed,
)
from jsonpatch.pydantic import JsonPatchFor, make_json_patch_body
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.standard import JsonPatch, apply_patch
from jsonpatch.types import JSONPointer, JSONValue

__all__ = [
    # exceptions
    "InvalidJSONPointer",
    "InvalidJsonPatch",
    "InvalidOperationSchema",
    "InvalidOperationRegistry",
    "PatchApplicationError",
    "PatchError",
    "PatchExecutionError",
    "PatchFailureDetail",
    "TestOpFailed",
    # types
    "JSONPointer",
    "JSONValue",
    # operation specs
    "OperationSchema",
    "OperationRegistry",
    # pydantic helpers
    "JsonPatchFor",
    "make_json_patch_body",
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
