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
from jsonpatch.types import JSONPointer, JSONValue


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
) -> (
    tuple[MutableMapping[str, JSONValue], str]
    | tuple[MutableSequence[JSONValue], int | Literal["-"]]
):
    """
    Return `(container, key)` such that `container[key]` is the target of the path.

    Args:
        doc (JSONValue): A JSON document, assumed to be valid.
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
    assert not is_root(path), "tried to resolve a path to last, but got root"
    ptr = cast_to_pointer(path)

    try:
        container, key = ptr.to_last(doc)
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
    except KeyError as e:
        raise PatchApplicationError(
            f"key '{key}' does not exist at location '{path}'"
        ) from e
    except IndexError as e:
        raise PatchApplicationError(f"index '{key}' is out of range at '{path}'") from e
    except TypeError as e:
        raise PatchApplicationError("array cannot be accessed with '-' key") from e


def add(doc: JSONValue, path: JSONPointer, value: JSONValue) -> JSONValue:
    if is_root(path):
        return value

    container, key = resolve_last(doc, path)

    if isinstance(container, MutableMapping):
        container[key] = value  # type: ignore[index]
    elif isinstance(container, MutableSequence):
        index = key if key != "-" else len(container)
        if index > len(container):  # type: ignore[operator]
            raise PatchApplicationError("couldn't insert outside of list")
        container.insert(index, value)  # type: ignore[arg-type]
    return doc


def remove(doc: JSONValue, path: JSONPointer) -> JSONValue:
    if is_root(path):
        # Sensible default for deleting root. Users can always customize RemoveOperation to forbid deleting root.
        # Reasoning: json.loads('null') is valid, json.loads('') is invalid. The former is empty JSON, latter is invalid.
        return None
    try:
        get(doc, path)
    except PatchApplicationError as e:
        raise PatchApplicationError(
            f"the target location '{path}' does not exist and cannot be removed"
        ) from e

    container, key = resolve_last(doc, path)
    del container[key]  # type: ignore[arg-type]
    return doc


def replace(
    doc: JSONValue,
    path: JSONPointer,
    value: JSONValue,
) -> JSONValue:
    try:
        get(doc, path)
    except PatchApplicationError as e:
        raise PatchApplicationError(
            f"the target location '{path}' does not exist and cannot be replaced"
        ) from e
    return add(doc, path, value)


def move(
    doc: JSONValue,
    from_path: JSONPointer,
    to_path: JSONPointer,
    *,
    forbid_nested: bool = True,
) -> JSONValue:
    from_ptr, to_ptr = (
        cast_to_pointer(from_path),
        cast_to_pointer(to_path),
    )  # catch pointer errors early
    if is_root(to_path):
        return get(doc, from_path)  # replace root
    if from_path == to_path:
        return doc  # no-op

    # check if this is a nested move
    is_nested: bool = is_root(from_path) or to_ptr.contains(
        from_ptr
    )  # there is a bug in JsonPointer where no pointer contains the root pointer

    value = get(doc, from_path)
    if is_nested:
        if forbid_nested:
            raise PatchApplicationError(
                f"the 'from' location '{from_path}' is a proper prefix of the 'path' location '{to_path}', "
                f"but a location cannot be moved into one of its children"
            )
        else:
            value = deepcopy(value)

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
    value = get(doc, from_path)
    value_copy = deepcopy(value)
    return add(doc, to_path, value_copy)


def test(doc: JSONValue, path: JSONPointer, value: JSONValue) -> JSONValue:
    curr = get(doc, path)
    if curr != value:
        raise TestOpFailed(
            f"test at path '{path}' failed, got {curr} but expected {value}"
        )
    return doc
