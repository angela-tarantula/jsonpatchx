"""
Showcase error semantics: expected vs unexpected failures.

Run:
  python -m examples.standard.failures
"""

from __future__ import annotations

import json
from typing import Literal, override

from examples._shared.error_cases import (
    EXPLODE_PATCH,
    INVALID_POINTER_PATCH,
    OUT_OF_RANGE_REMOVE_PATCH,
    TEST_FAILS_PATCH,
    TYPE_GATED_INCREMENT_PATCH,
)
from examples.custom_ops.custom_ops import IncrementOp
from jsonpatch import JsonPatch, OperationRegistry
from jsonpatch.exceptions import (
    InvalidJSONPointer,
    PatchApplyFailed,
    PatchError,
    TestOpFailed,
)
from jsonpatch.schema import OperationSchema
from jsonpatch.types import JSONPointer, JSONValue


class ExplodeOp(OperationSchema):
    op: Literal["explode"] = "explode"
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        _ = self.path.get(doc)
        return 1 / 0


def _print_detail(exc: PatchApplyFailed) -> None:
    detail = exc.detail
    print("  detail.index:", detail.index)
    print("  detail.op:", json.dumps(detail.op.model_dump(mode="json", by_alias=True)))
    print("  detail.cause_type:", detail.cause_type)
    print("  detail.message:", detail.message)


def main() -> None:
    doc: JSONValue = {"title": "Example", "trial": False, "tags": ["admin"]}

    print("Case A: expected TestOpFailed")
    try:
        JsonPatch(TEST_FAILS_PATCH).apply(doc)
    except TestOpFailed as exc:
        print("  caught:", type(exc).__name__)
        print("  message:", str(exc))

    print("\nCase B: invalid pointer syntax")
    try:
        OperationRegistry.standard().parse_python_patch(INVALID_POINTER_PATCH)
    except InvalidJSONPointer as exc:
        print("  caught:", type(exc).__name__)
        print("  message:", str(exc))

    print("\nCase C: type-gated pointer read failure")
    try:
        registry = OperationRegistry.with_standard(IncrementOp)
        JsonPatch(TYPE_GATED_INCREMENT_PATCH, registry=registry).apply(doc)
    except PatchError as exc:
        print("  caught:", type(exc).__name__)
        print("  message:", str(exc))

    print("\nCase D: array index out of range")
    try:
        JsonPatch(OUT_OF_RANGE_REMOVE_PATCH).apply(doc)
    except PatchError as exc:
        print("  caught:", type(exc).__name__)
        print("  message:", str(exc))

    print("\nCase E: unexpected exception wrapping")
    try:
        registry = OperationRegistry.with_standard(ExplodeOp)
        JsonPatch(EXPLODE_PATCH, registry=registry).apply(doc)
    except PatchApplyFailed as exc:
        print("  caught:", type(exc).__name__)
        _print_detail(exc)


if __name__ == "__main__":
    main()
