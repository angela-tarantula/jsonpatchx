"""
jsonpatch
---------

A modern, strongly-typed JSON Patch implementation powered by Pydantic.

Public API surface:

- Exceptions:
    - InvalidOperationSchema
    - OperationValidationError
    - InvalidOperationRegistry
    - InvalidJsonPatch
    - PatchApplicationError
    - PatchError
    - TestOpFailed

- Core types:
    - JsonPointerType
    - JsonValueType

- Operatation Specs:
    - OperationSchema
    - OperationRegistry

- Classics:
    - JsonPatch
    - apply_patch
"""

from __future__ import annotations

from jsonpatch.exceptions import (
    InvalidJsonPatch,
    InvalidOperationRegistry,
    InvalidOperationSchema,
    OperationValidationError,
    PatchApplicationError,
    PatchError,
    TestOpFailed,
)
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.standard import JsonPatch, apply_patch
from jsonpatch.types import JsonPointerType, JsonTextType, JsonValueType

__all__ = [
    # exceptions
    "InvalidJsonPatch",
    "InvalidOperationSchema",
    "InvalidOperationRegistry",
    "OperationValidationError",
    "PatchApplicationError",
    "PatchError",
    "TestOpFailed",
    # types
    "JsonPointerType",
    "JsonTextType",
    "JsonValueType",
    # operation specs
    "OperationSchema",
    "OperationRegistry",
    # classics
    "JsonPatch",
    "apply_patch",
]
