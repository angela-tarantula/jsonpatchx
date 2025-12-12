from collections.abc import Hashable
from typing import MutableMapping, MutableSequence

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)

from jsonpatch.exceptions import PatchApplicationError
from jsonpatch.types import JsonPointerType, JsonValueType


def _ensure_pointer(path: JsonPointerType) -> JsonPointer:
    """Cast a JsonPointerType into a JsonPointer."""
    if isinstance(path, JsonPointer):
        return path
    try:
        return JsonPointer(path)
    except JsonPointerException as e:
        raise PatchApplicationError(f"string '{path}' is not a jsonpointer") from e


def resolve_last(
    doc: JsonValueType,
    pointer: JsonPointerType,
) -> tuple[JsonValueType, Hashable]:
    """
    Return (container, key) such that container[key] is the target.

    - If path is the root, returns (doc, None).
    - Raises PatchApplicationError on resolution failure.
    """
    ptr = _ensure_pointer(pointer)
    try:
        return ptr.to_last(doc)  # type: ignore[no-any-return]
    except JsonPointerException as e:
        raise PatchApplicationError(str(e)) from e


def ensure_mapping(obj: JsonValueType, pointer: JsonPointerType) -> None:
    ptr = _ensure_pointer(pointer)
    if not isinstance(obj, MutableMapping):
        raise PatchApplicationError(f"Expected object at {ptr.path}")


def ensure_sequence(obj: JsonValueType, pointer: JsonPointerType) -> None:
    ptr = _ensure_pointer(pointer)
    if not isinstance(obj, MutableSequence):
        raise PatchApplicationError(f"Expected array at {ptr.path}")
