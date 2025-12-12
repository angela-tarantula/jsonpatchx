from collections.abc import Hashable
from typing import MutableMapping, MutableSequence

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)

from jsonpatch.exceptions import PatchApplicationError
from jsonpatch.types import JsonPointerType, JsonValueType

# NOTE: The JSON document is assumed to be valid. This has certain implications:
#   1. Dicts must have string keys


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

    - If pointer is the root, returns (doc, None).
    - Raises PatchApplicationError on resolution failure.
    """
    ptr = _ensure_pointer(pointer)
    try:
        return ptr.to_last(doc)  # type: ignore[no-any-return] #
    except JsonPointerException as e:
        raise PatchApplicationError(str(e)) from e


def resolve_last_mapping(
    doc: JsonValueType, pointer: JsonPointerType
) -> tuple[MutableMapping[str, JsonValueType], Hashable]:
    subobj, part = resolve_last(doc, pointer)
    if not isinstance(subobj, MutableMapping):
        raise PatchApplicationError(f"Expected object at {pointer}")
    return subobj, part


def resolve_last_sequence(
    doc: JsonValueType, pointer: JsonPointerType
) -> tuple[MutableMapping[str, JsonValueType], Hashable]:
    subobj, part = resolve_last(doc, pointer)
    if not isinstance(subobj, MutableSequence):
        raise PatchApplicationError(f"Expected array at {pointer}")
    return subobj, part  # type: ignore[return-value] # if doc is valid JSON, the mapping must have string keys


def get(doc: JsonValueType, pointer: JsonPointerType) -> JsonValueType:
    subobj, part = resolve_last(doc, pointer)
    if part is None:
        return subobj
    try:
        return subobj[part]  # type: ignore[index] # if invalid, raise error
    except (KeyError, IndexError) as e:
        raise PatchApplicationError(str(e))
