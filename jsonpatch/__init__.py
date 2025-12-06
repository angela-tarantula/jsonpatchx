# jsonpatch/__init__.py

"""
jsonpatch
---------

A modern, strongly-typed JSON Patch implementation powered by Pydantic.

Public API surface:

- Exceptions:
    - InvalidOperationSchema
    - InvalidPatchSchema
    - PatchApplicationError
    - PatchError
    - TestOpFailed

- Core types:
    - JsonPointerType
    - JsonValueType

- Schema system:
    - OperationSchema
    - PatchSchema

Built-in operations that live in ``jsonpatch.ops_builtin``:

 - OperationSchemas:
    - AddOp
    - RemoveOp
    - ReplaceOp
    - MoveOp
    - CopyOp
    - TestOp

 - PatchSchemas:
    - BuiltinPatchSchema

 - TypeAliases:
    - OpUnion

 - TypeAdapters:
    - BuiltinOpAdapter
    - BuiltinPatchAdapter
"""

from __future__ import annotations

from jsonpatch.exceptions import (
    InvalidOperationSchema,
    InvalidPatchSchema,
    PatchApplicationError,
    PatchError,
    TestOpFailed,
)
from jsonpatch.schema import OperationSchema, PatchSchema
from jsonpatch.types import JsonPointerType, JsonValueType

__all__ = [
    # exceptions
    "InvalidOperationSchema",
    "InvalidPatchSchema",
    "PatchApplicationError",
    "PatchError",
    "TestOpFailed",
    # types
    "JsonPointerType",
    "JsonValueType",
    # schema system
    "OperationSchema",
    "PatchSchema",
]
