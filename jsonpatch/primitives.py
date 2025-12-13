"""
Primitive helper functions for defining custom `apply()` in OperationSchemas.`

Assumes valid inputs.
"""

from typing import Literal, MutableMapping, MutableSequence

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)

from jsonpatch.exceptions import PatchApplicationError
from jsonpatch.types import JsonPointerType, JsonValueType


def is_root(path: JsonPointerType) -> bool:
    """True if the path points to root."""
    return str(path) == ""


def _cast_to_pointer(path: JsonPointerType) -> JsonPointer:
    """
    This is no-op if Pydantic pre-validates JsonPointerTypes, but users can opt out of
    pre-validation by annotating their path variables as str. This functions ensures
    that any strings intended to be used as jsonpointers have the proper syntax.
    """
    if isinstance(path, JsonPointer):
        return path
    try:
        return JsonPointer(path)
    except JsonPointerException as e:
        raise PatchApplicationError(f"string '{path}' is not a jsonpointer") from e


def resolve_last(
    doc: JsonValueType, path: JsonPointerType
) -> (
    tuple[MutableMapping[str, JsonValueType], str]
    | tuple[MutableSequence[JsonValueType], int | Literal["-"]]
):
    """
    Return (container, key) such that container[key] is the target.

    Args:
        doc (JsonValueType): A JSON document, assumed to be valid.
        path (JsonPointerType): A jsonpointer, not assumed to be valid.
                                May not point to root (nothing to resolve).

    Details:
        The target can be set or overwritten with `container[key] = value`.
        The target can be removed with `del container[key]`.
        The target can be accessed with `value = container[key]`.
        But the key is not guaranteed to a valid index/key of the container.
        If the key is invalid, trying container[key] will raise KeyError or TypeError.

    Returns:
        (container, key)
        When the container is a sequence, the index will be a positive integer or "-".
        When the container is a mapping, the index will be a string.
    """
    assert not is_root(path), "the root has no path to resolve"
    ptr = _cast_to_pointer(path)

    try:
        return ptr.to_last(doc)  # type: ignore[no-any-return]
    except JsonPointerException as e:
        raise PatchApplicationError(str(e)) from e


def resolve_last_mapping(
    doc: JsonValueType, path: JsonPointerType
) -> tuple[MutableMapping[str, JsonValueType], str]:
    """Confirms that a jsonpointer leads to a JSON object. Returns (mapping, key)."""
    mapping, key = resolve_last(doc, path)
    if not isinstance(mapping, MutableMapping):
        raise PatchApplicationError(f"Expected object at {path}")
    return mapping, key  # type: ignore[return-value]


def resolve_last_sequence(
    doc: JsonValueType, path: JsonPointerType
) -> tuple[MutableSequence[JsonValueType], int | Literal["-"]]:
    """Confirms that a jsonpointer leads to a JSON array. Returns (array, key)."""
    array, key = resolve_last(doc, path)
    if not isinstance(array, MutableSequence):
        raise PatchApplicationError(f"Expected array at {path}")
    return array, key  # type: ignore[return-value]


def get(doc: JsonValueType, path: JsonPointerType) -> JsonValueType:
    if is_root(path):
        return doc

    container, key = resolve_last(doc, path)

    try:
        return container[key]  # type: ignore[index]
    except (KeyError, IndexError) as e:
        raise PatchApplicationError(str(e)) from e
    except TypeError as e:
        raise PatchApplicationError("array cannot be accessed with '-' key") from e


def set(
    doc: JsonValueType, path: JsonPointerType, value: JsonValueType
) -> JsonValueType:
    if is_root(path):
        return value

    container, key = resolve_last(doc, path)

    if key == "-" and isinstance(container, MutableSequence):
        container.append(value)
    else:
        try:
            container[key] = value  # type: ignore[index]
        except (KeyError, IndexError) as e:
            raise PatchApplicationError(str(e)) from e
    return doc
