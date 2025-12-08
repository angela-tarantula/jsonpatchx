# jsonpatch/__init__.py

"""
jsonpatch
---------

A modern, strongly-typed JSON Patch implementation powered by Pydantic.

Public API surface:

- Exceptions:
    - InvalidOperationSchema
    - InvalidOperationRegistry
    - PatchApplicationError
    - PatchError
    - TestOpFailed

- Core types:
    - JsonPointerType
    - JsonValueType

- Operatation Specs:
    - OperationSchema
    - OperationRegistry
"""

from __future__ import annotations

from jsonpatch.exceptions import (
    InvalidOperationRegistry,
    InvalidOperationSchema,
    PatchApplicationError,
    PatchError,
    TestOpFailed,
)
from jsonpatch.registry import OperationRegistry
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JsonPointerType, JsonValueType

__all__ = [
    # exceptions
    "InvalidOperationSchema",
    "InvalidOperationRegistry",
    "PatchApplicationError",
    "PatchError",
    "TestOpFailed",
    # types
    "JsonPointerType",
    "JsonValueType",
    # operation specs
    "OperationSchema",
    "OperationRegistry",
]
