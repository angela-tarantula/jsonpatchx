"""
Primitive helper functions for defining custom `apply()` in OperationSchemas`. They all assume `doc` is valid JSON-serializable.

Mypy is not yet advanced enough to narrow the union of tuples: https://github.com/python/mypy/issues/9791.
For example, when `resolve_last` returns a `(container, key)` in which `container` is a `MutableMapping`, mypy is
unable to deduce that `key` must be a `str`. Most `type: ignore` are workarounds for this false-positive.
I did not want to litter the implementations with `typing.cast` calls. Hopefully that issue gets fixed.

The only JsonPointer operations this library depends on are JsonPointer.to_last() and JsonPointer.contains().
This is by design to minimize tight coupling and make it easy to provide custom jsonpointer classes that
follow the two-function Protocol.

# A limitation of JsonPointer is accepting negative indices for JSON arrays. To enable this feature, custom JsonPointer is required.
"""

from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence
from copy import deepcopy
from functools import lru_cache
from typing import Literal, overload

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)

from jsonpatch.exceptions import PatchApplicationError, TestOpFailed
from jsonpatch.types import (
    JSONArray,
    JSONObject,
    JSONPointer,
    JSONValue,
    MutableJSONArray,
    MutableJSONObject,
)


def are_equal(
    first: JSONValue, second: JSONValue
) -> bool:  # TODO: just use orjson and compare strings?
    """
    Compare two JSON-like values for semantic equality.

    This function defines equality according to JSON rules rather than
    Python's default equality semantics. In particular:

    - Booleans are not considered equal to numbers (e.g., `True != 1`).
    - Integers and floats are compared numerically (e.g., `1 == 1.0`).
    - Mappings (dict-like objects) are compared by keys and values,
      regardless of their concrete class (e.g., `dict` vs `defaultdict`).
    - Sequences (list-like objects) are compared by order and contents,
      regardless of their concrete class.
    - Comparison is recursive for nested structures.

    Args:
        first (JSONValue): First JSON value
        second (JSONValue): Second JSON value

    Returns:
        equality_result (bool): True if the two values are JSON-semantically equal, False otherwise.
    """

    # Reject mismatched types for JSON primitives
    if isinstance(first, bool) or isinstance(second, bool):
        # Make sure both are bool (avoid True == 1)
        if type(first) is bool and type(second) is bool:
            return first == second
        return False

    # Numbers: both must be int/float (but not bool)
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return float(first) == float(second)  # TODO: avoid lossy conversion

    # Strings and null
    if isinstance(first, str) and isinstance(second, str):
        return first == second
    if first is None and second is None:
        return True

    # Mapping types (e.g., dict, defaultdict, custom dict-like)
    if isinstance(first, Mapping) and isinstance(second, Mapping):
        if set(first.keys()) != set(second.keys()):
            return False
        return all(
            are_equal(first[k], second[k]) for k in first
        )  # optimization: the DFS can be iterative to avoid stackoverflow

    # Sequence types (e.g., list, deque, custom list-like) but not str
    if (
        isinstance(first, Sequence)
        and isinstance(second, Sequence)
        and not isinstance(first, str)
        and not isinstance(second, str)
    ):
        if len(first) != len(second):
            return False
        return all(are_equal(a, b) for a, b in zip(first, second))

    return False


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


@overload
def resolve_last(
    doc: JSONValue,
    path: JSONPointer,
    *,
    exists: Literal[True],
    mutable: Literal[True],
    container: Literal["object", "array"] | None = None,
) -> tuple[MutableJSONObject, str] | tuple[MutableJSONArray, int]: ...


@overload
def resolve_last(
    doc: JSONValue,
    path: JSONPointer,
    *,
    exists: Literal[False] | None = None,
    mutable: Literal[True],
    container: Literal["object", "array"] | None = None,
) -> tuple[MutableJSONObject, str] | tuple[MutableJSONArray, int | Literal["-"]]: ...


@overload
def resolve_last(
    doc: JSONValue,
    path: JSONPointer,
    *,
    exists: Literal[True],
    mutable: bool | None = None,
    container: Literal["object", "array"] | None = None,
) -> tuple[JSONObject, str] | tuple[JSONArray, int]: ...


@overload
def resolve_last(
    doc: JSONValue,
    path: JSONPointer,
    *,
    exists: bool | None = None,
    mutable: bool | None = None,
    container: Literal["object", "array"] | None = None,
) -> tuple[JSONObject, str] | tuple[JSONArray, int | Literal["-"]]: ...


def resolve_last(
    doc: JSONValue,
    path: JSONPointer,
    *,
    exists: bool | None = None,
    mutable: bool | None = None,
    container: Literal["object", "array"] | None = None,
) -> tuple[JSONObject, str] | tuple[JSONArray, int | Literal["-"]]:
    """
    Resolve a JSON Pointer to its parent container and final token.

    This function resolves `path` against `doc` and returns `(container, key)` such that
    `container[key]` refers to the value designated by `path` (i.e., the `path`'s *target*).

    - The target can be accessed with `value = container[key]`.
    - The target can be set or overwritten with `container[key] = value`.
    - The target can be removed with `del container[key]`.
    - If target does not exist, accessing `container[key]` will raise `KeyError`, `IndexError`, or `TypeError`

    Parameters
    ----------
    doc:
        JSON document to resolve against (assumed valid).
    path:
        JSON Pointer to resolve. Must not point to the root (there is no “parent” to return).

    Keyword-only parameters
    -----------------------
    exists:
        Requires the target to exist or not (for JSONObject: if `key` is present; for arrays: if `key` is valid index):
        - True  -> target must exist
        - False -> target must not exist
        - None (default) -> neither is enforced
    mutable:
        Controls the required mutability of the resolved container:
        - True  -> container must be mutable
        - False -> container must be immutable
        - None (default) -> neither is enforced
    container:
        Optionally constrain the expected container type:
        - "object" -> JSONObject only
        - "array"  -> JSONArray only
        - None (default) -> neither is enforced

    Returns
    -------
    (container, key):
        A tuple consisting of:
        - `container`: the resolved parent container (JSONObject or JSONArray)
        - `key`: the final token of the pointer
            * JSONObject key: `str`
            * JSONArray index: `int` (non-negative) or `"-"`. If `exists=True`,
                            it will always be a non-negative `int` within bounds.

    Raises
    ------
    PatchApplicationError:
        - if `path` points to the root
        - if `path` on `doc` cannot be resolved
        - if `exists=True` and the target does not exist
        - if `exists=False` and the target does exist
        - if `container="object"` but the container is not a JSONObject
        - if `container="array"` but the container is not a JSONArray
        - if `mutable=True` but the container is not mutable
        - if `mutable=False` but the container is mutable
    """
    if is_root(path):
        raise PatchApplicationError("tried to resolve a path to last, but got root")

    ptr = cast_to_pointer(path)

    try:
        path_container, path_key = ptr.to_last(doc)
        assert isinstance(path_container, (Mapping, Sequence)) and not isinstance(
            path_container, (str, bytes, bytearray)
        ), "JsonPointer implementation changed"  # TODO: confirm this
    except JsonPointerException as e:
        raise PatchApplicationError(f"unable to resolve path '{path}': {e}") from e

    # container check
    if container == "object":
        if not isinstance(path_container, Mapping):
            raise PatchApplicationError(
                f"expected object container at '{path}', got {type(path_container)!r}"
            )
    elif container == "array":
        if not isinstance(path_container, Sequence):
            raise PatchApplicationError(
                f"expected array container at '{path}', got {type(path_container)!r}"
            )

    # mutability check
    if mutable is not None:
        is_mutable = isinstance(path_container, (MutableMapping, MutableSequence))
        if is_mutable is not mutable:
            if mutable:
                raise PatchApplicationError(
                    f"expected mutable container at '{path}', got {type(path_container)!r}"
                )
            raise PatchApplicationError(
                f"expected immutable container at '{path}', got {type(path_container)!r}"
            )

    # existence check
    try:
        path_container[path_key]
    except (KeyError, IndexError, TypeError) as e:
        # missing key, index out of bounds, or using "-" on array
        if exists:
            raise PatchApplicationError(f"target at '{path}' does not exist") from e
    else:
        if exists is False:
            raise PatchApplicationError(f"target at '{path}' exists")

    return path_container, path_key


def assert_valid(doc: JSONValue, *paths: JSONPointer) -> None:
    for path in paths:
        if not is_root(path):
            resolve_last(doc, path)


def assert_targets(
    doc: JSONValue,
    *paths: JSONPointer,
    exists: bool | None = None,
    mutable: bool | None = None,
) -> None:
    for path in paths:
        if not is_root(path):
            resolve_last(doc, path, exists=exists, mutable=mutable)


def is_parent_path(*, parent_path: JSONPointer, child_path: JSONPointer) -> bool:
    # Need to handle the root case separately for now due to a bug in JsonPointer.contains()
    # wherein any jp1.contains(jp2)==False for all jp1 whenever jp2 is the root jsonpointer.
    if is_root(parent_path):
        return True

    parent_ptr, child_ptr = cast_to_pointer(parent_path), cast_to_pointer(child_path)
    return child_ptr.contains(parent_ptr)  # type: ignore[no-any-return] # JsonPatch is untyped, but this is correct


def get(doc: JSONValue, path: JSONPointer) -> JSONValue:
    if is_root(path):
        return doc
    container, key = resolve_last(doc, path, exists=True)
    return container[key]  # type: ignore[index] # mypy is not advanced enough to narrow tuples


def add(doc: JSONValue, path: JSONPointer, value: JSONValue) -> JSONValue:
    if is_root(path):
        return value  # replace root

    container, key = resolve_last(doc, path, mutable=True)

    if isinstance(container, MutableMapping):
        container[key] = value  # type: ignore[index] # mypy is not advanced enough to narrow tuples
    elif isinstance(container, MutableSequence):
        if key == "-":
            key = len(container)
        # we know key is an int now, but mypy isn't smart enough yet
        if key > len(container):  # type: ignore[operator]
            raise PatchApplicationError(f"target at '{path}' is out of range")
        assert key >= 0, "JsonPointer implementation changed"  # type: ignore[operator]
        container.insert(key, value)  # type: ignore[arg-type]
    return doc


def remove(doc: JSONValue, path: JSONPointer) -> JSONValue:
    if is_root(path):
        raise PatchApplicationError("cannot remove the root")
    container, key = resolve_last(doc, path, exists=True, mutable=True)
    del container[key]  # type: ignore[arg-type] # mypy is not advanced enough to narrow tuples
    return doc


def replace(
    doc: JSONValue,
    path: JSONPointer,
    value: JSONValue,
) -> JSONValue:
    if is_root(path):
        return value  # replace root
    doc_intermediate = remove(doc, path)
    return add(doc_intermediate, path, value)


def move(
    doc: JSONValue,
    from_path: JSONPointer,
    to_path: JSONPointer,
) -> JSONValue:
    assert_targets(doc, from_path, exists=True, mutable=True)
    if from_path == to_path:
        return doc  # no-op
    if is_root(to_path):
        return get(doc, from_path)  # replace root

    # check if this is a nested move
    if is_parent_path(parent_path=from_path, child_path=to_path):
        raise PatchApplicationError(
            f"path '{from_path}' cannot be moved into its child path '{to_path}'"
        )

    value = get(doc, from_path)
    doc_intermediate = remove(doc, from_path)
    return add(doc_intermediate, to_path, value)


def copy(
    doc: JSONValue,
    from_path: JSONPointer,
    to_path: JSONPointer,
) -> JSONValue:
    value = get(doc, from_path)
    if from_path == to_path:
        return doc  # no-op
    value_copy = deepcopy(value)
    return add(doc, to_path, value_copy)


def test(doc: JSONValue, path: JSONPointer, expected: JSONValue) -> JSONValue:
    value = get(doc, path)
    if not are_equal(value, expected):
        raise TestOpFailed(
            f"test at path '{path}' failed, got {value} but expected {expected}"
        )
    return doc


def swap(
    doc: JSONValue, first_path: JSONPointer, second_path: JSONPointer
) -> JSONValue:
    assert_targets(doc, first_path, second_path, exists=True, mutable=True)
    if first_path == second_path:
        return doc  # no-op
    if is_root(first_path):
        return get(doc, second_path)
    if is_root(second_path):
        return get(doc, first_path)

    # check if this is a nested swap
    for parent, child in [(first_path, second_path), (second_path, first_path)]:
        if is_parent_path(parent_path=parent, child_path=child):
            raise PatchApplicationError(
                f"path '{parent}' cannot be moved into its child path '{child}'"
            )

    first_path_value = get(doc, first_path)
    doc_intermediate = move(doc, second_path, first_path)
    return add(doc_intermediate, second_path, first_path_value)
