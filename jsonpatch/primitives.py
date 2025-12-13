"""
Primitive helper functions for defining custom `apply()` in OperationSchemas.`

Mypy is not yet advanced enough to narrow the union of tuples: https://github.com/python/mypy/issues/9791.
For example, when `resolve_last` returns a `(container, key)` in which `container` is a `Mapping`, mypy is
unable to deduce that `key` must be a `str`. Most `type: ignore` are workarounds for this false-positive.
I did not want to litter the implementations with `typing.cast` calls. Hopefully that issue gets fixed.
"""

from collections.abc import Mapping, Sequence
from typing import Literal, MutableMapping, MutableSequence

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)

from jsonpatch.exceptions import PatchApplicationError
from jsonpatch.types import JsonPointerType, JsonValueType


def is_root(path: JsonPointerType) -> bool:
    """`True` if the `path` points to root, `False` otherwise."""
    return str(path) == ""


def cast_to_pointer(path: JsonPointerType) -> JsonPointer:
    """
    This is no-op if `Pydantic` pre-validates `JsonPointerTypes`, but users can opt out of
    pre-validation by annotating their path variables as `str`. This functions ensures
    that any paths intended to be used as jsonpointers have the proper syntax.
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
    tuple[Mapping[str, JsonValueType], str]
    | tuple[Sequence[JsonValueType], int | Literal["-"]]
):
    """
    Return `(container, key)` such that `container[key]` is the target of the path.

    Args:
        doc (JsonValueType): A JSON document, assumed to be valid.
        path (JsonPointerType): A jsonpointer, not assumed to be valid.
                                May not point to root (nothing to resolve).


    Returns:
        `(container, key)`
        - When the container is a `Sequence`, the index will be a non-negative `int` or `Literal["-"]`.
        - When the container is a `Mapping`, the index will be a string.
        - The target can be set or overwritten with `container[key] = value`.
        - The target can be removed with `del container[key]`.
        - The target can be accessed with `value = container[key]`.
        - But the key is not guaranteed to a valid index/key of the container.
        - If the key is invalid, trying `container[key]` will raise `KeyError` or `TypeError`.
    """
    assert not is_root(path), "the root has no path to resolve"
    ptr = cast_to_pointer(path)

    try:
        return ptr.to_last(doc)  # type: ignore[no-any-return]
    except JsonPointerException as e:
        raise PatchApplicationError(str(e)) from e


def resolve_last_mapping(
    doc: JsonValueType, path: JsonPointerType
) -> tuple[MutableMapping[str, JsonValueType], str]:
    """Confirms that `path`, a jsonpointer, leads to a JSON object (`Mapping`). Returns `(mapping, key)`."""
    mapping, key = resolve_last(doc, path)
    if not isinstance(mapping, MutableMapping):
        raise PatchApplicationError(f"Expected object at {path}")
    return mapping, key  # type: ignore[return-value]


def resolve_last_sequence(
    doc: JsonValueType, path: JsonPointerType
) -> tuple[MutableSequence[JsonValueType], int | Literal["-"]]:
    """Confirms that `path`, a jsonpointer, leads to a JSON array (`Sequence`). Returns `(array, key)`."""
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

    if isinstance(container, MutableMapping):
        try:
            container[key] = value
        except KeyError as e:
            raise PatchApplicationError(str(e)) from e
    elif isinstance(container, MutableSequence):
        index = key if key != "-" else len(container)
        if index > len(container):  # type: ignore[operator]
            raise PatchApplicationError("can't insert outside of list")
        container.insert(index, value)  # type: ignore[arg-type]
    else:
        raise PatchApplicationError(
            f"jsonpointer '{path}' points to immutable {type(container).__class__.__name__}, "
            f"cannot set '{value}' at '{key}'"
        )
    return doc
