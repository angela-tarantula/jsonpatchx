"""
Primitive helper functions for defining custom `apply()` in OperationSchemas.`

Mypy is not yet advanced enough to narrow the union of tuples: https://github.com/python/mypy/issues/9791.
For example, when `resolve_last` returns a `(container, key)` in which `container` is a `Mapping`, mypy is
unable to deduce that `key` must be a `str`. Most `type: ignore` are workarounds for this false-positive.
I did not want to litter the implementations with `typing.cast` calls. Hopefully that issue gets fixed.

The only JsonPointer operations this library depends on are JsonPointer.to_last() and JsonPointer.contains().
This is by design to minimize tight coupling and make it easy to provide custom jsonpointer classes that
follow the two-function Protocol.
"""

from copy import deepcopy
from functools import lru_cache
from typing import Literal, MutableMapping, MutableSequence

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)

from jsonpatch.exceptions import PatchApplicationError, TestOpFailed
from jsonpatch.types import JSONArray, JSONObject, JSONPointer, JSONString, JSONValue


def is_root(path: JSONPointer) -> bool:
    """`True` if the `path` points to root, `False` otherwise."""
    return path == ""


@lru_cache
def cast_to_pointer(path: JSONPointer) -> JsonPointer:
    try:
        return JsonPointer(path)
    except (
        JsonPointerException
    ) as e:  # defensive - if user opts out of Pydantic pre-validation
        raise PatchApplicationError(f"expected '{path}' to be a jsonpointer") from e


def resolve_last(
    doc: JSONValue, path: JSONPointer
) -> tuple[JSONObject, JSONString] | tuple[JSONArray, int | Literal["-"]]:
    """
    Get `(container, key)` such that `container[key]` is the target of the path.

    Args:
        doc (JSONValue): A JSON document, assumed to be valid.
        path (JSONPointer): A jsonpointer, not assumed to be valid.
                                Must not point to root (nothing to resolve).

    Raises:
        PatchApplicationError: If `path` points to the root, or if the resolved `container`
                                is neither `MutableMapping` nor `MutableSequence`.

    Returns:
        container_and_key (tuple[JSONObject, JSONString] | tuple[JSONArray, int | Literal["-"]]):
        A tuple `(container, key)` such that `container[key]` is the target of the path.
        - When the container is a `Sequence`, the index will be a non-negative `int` or `Literal["-"]`.
        - When the container is a `Mapping`, the index will be a string.
        - The target can be set or overwritten with `container[key] = value`.
        - The target can be removed with `del container[key]`.
        - The target can be accessed with `value = container[key]`.
        - But the key is not guaranteed to a valid index/key of the container.
        - If the key is invalid, trying `container[key]` will raise `KeyError` or `TypeError`.
    """
    assert not is_root(path), "tried to resolve a path to last, but got root"
    ptr = cast_to_pointer(path)

    try:
        container, key = ptr.to_last(doc)
        # A limitation of JsonPointer is accepting negative indices for JSON arrays. To enable this feature, custom JsonPointer is required.
    except JsonPointerException as e:
        raise PatchApplicationError(str(e)) from e

    if not isinstance(container, (MutableMapping, MutableSequence)):
        raise PatchApplicationError(
            f"container at '{path}' is neither MutableMapping nor MutableSequence"
        )

    return container, key  # type: ignore[return-value]


def resolve_last_mapping(
    doc: JSONValue, path: JSONPointer
) -> tuple[MutableMapping[str, JSONValue], str]:
    """Confirms that `path`, a jsonpointer, leads to a JSON object (`Mapping`). Returns `(mapping, key)`."""
    mapping, key = resolve_last(doc, path)
    if not isinstance(mapping, MutableMapping):
        raise PatchApplicationError(f"expected object at '{path}'")
    return mapping, key  # type: ignore[return-value]


def resolve_last_sequence(
    doc: JSONValue, path: JSONPointer
) -> tuple[MutableSequence[JSONValue], int | Literal["-"]]:
    """Confirms that `path`, a jsonpointer, leads to a JSON array (`Sequence`). Returns `(array, key)`."""
    array, key = resolve_last(doc, path)
    if not isinstance(array, MutableSequence):
        raise PatchApplicationError(f"expected array at '{path}'")
    return array, key  # type: ignore[return-value]


def get(doc: JSONValue, path: JSONPointer) -> JSONValue:
    if is_root(path):
        return doc

    container, key = resolve_last(doc, path)

    try:
        return container[key]  # type: ignore[index]
    except (KeyError, IndexError, TypeError) as e:
        raise PatchApplicationError(f"target at '{path}' does not exist") from e


def add(doc: JSONValue, path: JSONPointer, value: JSONValue) -> JSONValue:
    if is_root(path):
        return value

    container, key = resolve_last(doc, path)

    if isinstance(container, MutableMapping):
        container[key] = value  # type: ignore[index]
    elif isinstance(container, MutableSequence):
        index = key if key != "-" else len(container)
        if index > len(container):  # type: ignore[operator]
            raise PatchApplicationError(f"target at '{path}' is out of range")
        container.insert(index, value)  # type: ignore[arg-type]
    return doc


def remove(doc: JSONValue, path: JSONPointer, *, strict: bool = True) -> JSONValue:
    if is_root(path):
        raise PatchApplicationError("cannot remove the root")

    try:
        get(doc, path)
    except PatchApplicationError as e:
        if strict:
            raise e  # path missing, give specific error
        else:
            return doc  # path already missing
    container, key = resolve_last(doc, path)
    del container[key]  # type: ignore[arg-type]
    return doc


def replace(
    doc: JSONValue,
    path: JSONPointer,
    value: JSONValue,
) -> JSONValue:
    if is_root(path):
        return value
    doc = remove(doc, path)
    return add(doc, path, value)


def move(
    doc: JSONValue,
    from_path: JSONPointer,
    to_path: JSONPointer,
) -> JSONValue:
    from_ptr, to_ptr = (
        cast_to_pointer(from_path),
        cast_to_pointer(to_path),
    )  # catch pointer errors early
    if from_path == to_path:
        return doc  # no-op
    if is_root(to_path):
        return get(doc, from_path)  # replace root

    # check if this is a nested move
    if (
        is_root(from_path) or to_ptr.contains(from_ptr)
    ):  # there is a bug in JsonPointer where no pointer is considered to 'contain' the root pointer, so must separately check if from_path is root
        raise PatchApplicationError(f"path '{to_path}' cannot contain '{from_path}'")

    value = get(doc, from_path)
    doc = remove(doc, from_path)
    return add(doc, to_path, value)


def copy(
    doc: JSONValue,
    from_path: JSONPointer,
    to_path: JSONPointer,
) -> JSONValue:
    _, __ = (
        cast_to_pointer(from_path),
        cast_to_pointer(to_path),
    )  # catch pointer errors early
    if from_path == to_path:
        return doc  # no-op
    value = get(doc, from_path)
    value = deepcopy(value)
    return add(doc, to_path, value)


def test(doc: JSONValue, path: JSONPointer, value: JSONValue) -> JSONValue:
    curr = get(doc, path)
    if curr != value:
        raise TestOpFailed(
            f"test at path '{path}' failed, got {curr} but expected {value}"
        )
    return doc


def swap(
    doc: JSONValue, first_path: JSONPointer, second_path: JSONPointer
) -> JSONValue:
    first_ptr, second_ptr = (
        cast_to_pointer(first_path),
        cast_to_pointer(second_path),
    )  # catch pointer errors early
    if first_path == second_path:
        return doc  # no-op
    if is_root(first_path):
        return get(doc, second_path)
    if is_root(second_path):
        return get(doc, first_path)

    # check if this is a nested swap
    if second_ptr.contains(first_ptr) or first_ptr.contains(second_ptr):
        parent, child = (
            (first_path, second_path)
            if second_ptr.contains(first_ptr)
            else (second_path, first_path)
        )
        raise PatchApplicationError(f"path '{parent}' cannot contain '{child}'")

    first_path_value = get(doc, first_path)
    doc = move(doc, second_path, first_path)
    return add(doc, second_path, first_path_value)
