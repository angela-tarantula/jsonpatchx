"""
jsonpatch

A modern, strongly-typed JSON Patch implementation powered by Pydantic.

Public API surface:

- Exceptions:
    - InvalidOperationSchema
    - InvalidOperationRegistry
    - InvalidJsonPatch
    - PatchApplicationError
    - PatchError
    - TestOpFailed

- Core types:
    - JSONPointer
    - JSONValue

- Operation specs:
    - OperationSchema
    - OperationRegistry

- Classics:
    - JsonPatch
    - apply_patch

- Built-ins:
    - STANDARD_OPS
    - AddOp
    - RemoveOp
    - ReplaceOp
    - MoveOp
    - CopyOp
    - TestOp

- Pydantic helpers:
    - JsonPatchFor
    - make_json_patch_body

- FastAPI helpers (optional dependency):
    - see ``jsonpatch.fastapi``
"""

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
    InvalidOperationRegistry,
    InvalidOperationSchema,
    PatchApplicationError,
    PatchError,
    TestOpFailed,
)
from jsonpatch.pydantic import JsonPatchFor, make_json_patch_body
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.standard import JsonPatch, apply_patch
from jsonpatch.types import JSONPointer, JSONValue

__all__ = [
    # exceptions
    "InvalidJsonPatch",
    "InvalidOperationSchema",
    "InvalidOperationRegistry",
    "PatchApplicationError",
    "PatchError",
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
