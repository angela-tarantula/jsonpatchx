"""
Primitive helper functions for defining custom `apply()` methods on `OperationSchema`
implementations.

These helpers centralize the tricky, low-level JSON Pointer and container manipulation
logic so that custom operations can be implemented declaratively in terms of:

    - "get the value at this JSON Pointer"
    - "add/replace/remove at this JSON Pointer"
    - "move/copy between JSON Pointers"
    - "transform/swap/append/extend/toggle/increment/decrement"


Type-checker note
-----------------
Mypy is not yet advanced enough to narrow the union of tuples returned by
`resolve_last()`: https://github.com/python/mypy/issues/9791. For example, if a
function returns tuple[str, int] | tuple[int, str], and you narrow the return type's
first element as a str, mypy still thinks the second element can be int | str. Most
`type: ignore` comments in this module are workarounds for that false positive and help
avoid littering the implementation with `typing.cast` calls.


JsonPointer dependency
----------------------
The only `JsonPointer` operations this library relies on are:

    - `JsonPointer.to_last(doc)`  → `(container, key)`
    - `JsonPointer.contains(other_pointer)` → bool

This is deliberate: it minimizes tight coupling to any particular `jsonpointer`
implementation and makes it easy to support custom pointer classes that satisfy
a simple two-method protocol.

Upstream limitation: the `jsonpointer` library does not accept negative indices
for JSON arrays. Supporting that would require upstream changes.
"""

from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence
from copy import deepcopy
from functools import lru_cache
from typing import Any, Callable, Literal, TypeVar, overload

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)

from jsonpatch.exceptions import PatchApplicationError, TestOpFailed
from jsonpatch.types import (
    JSONArray,
    JSONNumber,
    JSONObject,
    JSONPointer,
    JSONValue,
    MutableJSONArray,
    MutableJSONObject,
)

# NOTE: All of these primitives do rely on one thing: that `doc` is a valid JSON-serializable python object

U = TypeVar("U")
E = TypeVar("E", bound=JSONValue)


def are_equal(
    first: JSONValue, second: JSONValue
) -> bool:  # TODO: just use orjson and compare strings?
    """
    Compare two JSON-like values for semantic equality.

    This uses JSON-ish equality rules rather than Python's default equality:

    - Booleans are not equal to numbers (e.g., True != 1).
    - Integers and floats compare numerically (e.g., 1 == 1.0).
    - Objects compare by key-set and recursively by values.
    - Arrays compare by length and order and recursively by elements.
    """
    # Booleans: require both to be bool to compare (avoid True == 1)
    if isinstance(first, bool) or isinstance(second, bool):
        return type(first) is bool and type(second) is bool and first == second  # noqa: E721

    # Numbers
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return first == second

    # Strings
    if isinstance(first, str) and isinstance(second, str):
        return first == second

    # Null
    if first is None and second is None:
        return True

    # Objects
    if isinstance(first, Mapping) and isinstance(second, Mapping):
        if set(first.keys()) != set(second.keys()):
            return False
        return all(
            are_equal(first[k], second[k]) for k in first
        )  # if stackoverflow issue, use iterative BFS

    # Arrays (exclude string/bytes)
    if (
        isinstance(first, Sequence)
        and isinstance(second, Sequence)
        and not isinstance(first, (str, bytes, bytearray))
        and not isinstance(second, (str, bytes, bytearray))
    ):
        if len(first) != len(second):
            return False
        return all(
            are_equal(a, b) for a, b in zip(first, second)
        )  # if stackoverflow issue, use iterative BFS

    return False


def is_root(path: JSONPointer[Any]) -> bool:
    """Return True if and only if `path` points to the root (empty pointer)."""
    return path == ""


@lru_cache(maxsize=1024)
def cast_to_pointer(path: JSONPointer[Any]) -> JsonPointer:
    """
    Convert a (validated) `JSONPointer` value into an upstream `JsonPointer`.

    Defensive: if a caller bypasses Pydantic validation and passes invalid
    syntax, raise PatchApplicationError.
    """
    try:
        return JsonPointer(path)
    except JsonPointerException as e:
        raise PatchApplicationError(f"expected {path!r} to be a JSON Pointer") from e


@overload
def resolve_last(
    doc: JSONValue,
    path: JSONPointer[Any],
    *,
    exists: Literal[True],
    mutable: Literal[True],
    container: Literal["object", "array"] | None = None,
) -> (
    tuple[MutableJSONObject[JSONValue], str] | tuple[MutableJSONArray[JSONValue], int]
): ...


@overload
def resolve_last(
    doc: JSONValue,
    path: JSONPointer[Any],
    *,
    exists: Literal[False] | None = None,
    mutable: Literal[True],
    container: Literal["object", "array"] | None = None,
) -> (
    tuple[MutableJSONObject[JSONValue], str]
    | tuple[MutableJSONArray[JSONValue], int | Literal["-"]]
): ...


@overload
def resolve_last(
    doc: JSONValue,
    path: JSONPointer[Any],
    *,
    exists: Literal[True],
    mutable: bool | None = None,
    container: Literal["object", "array"] | None = None,
) -> tuple[JSONObject[JSONValue], str] | tuple[JSONArray[JSONValue], int]: ...


@overload
def resolve_last(
    doc: JSONValue,
    path: JSONPointer[Any],
    *,
    exists: bool | None = None,
    mutable: bool | None = None,
    container: Literal["object", "array"] | None = None,
) -> (
    tuple[JSONObject[JSONValue], str] | tuple[JSONArray[JSONValue], int | Literal["-"]]
): ...


def resolve_last(
    doc: JSONValue,
    path: JSONPointer[Any],
    *,
    exists: bool | None = None,
    mutable: bool | None = None,
    container: Literal["object", "array"] | None = None,
) -> (
    tuple[JSONObject[JSONValue], str] | tuple[JSONArray[JSONValue], int | Literal["-"]]
):
    """
    Resolve a JSON Pointer to its parent container and final token.

    Returns `(container, key)` such that `container[key]` is the target of `path`.

    Constraints (optional):
      - exists: require target existence (True) or non-existence (False)
      - mutable: require container mutability (True) or immutability (False)
      - container: require parent container to be "object" or "array"

    The root has no container and raises PatchApplicationError.
    """
    if is_root(path):
        raise PatchApplicationError(
            "tried to resolve a path to last, but got root, which has no container"
        )

    ptr = cast_to_pointer(path)

    try:
        path_container, path_key = ptr.to_last(doc)
        assert isinstance(path_container, (Mapping, Sequence)) and not isinstance(
            path_container, (str, bytes, bytearray)
        ), "JsonPointer implementation changed"
    except JsonPointerException as e:
        raise PatchApplicationError(f"unable to resolve path {path!r}: {e}") from e

    # container constraint
    if container == "object":
        if not isinstance(path_container, Mapping):
            raise PatchApplicationError(
                f"expected object container at {path!r}, got {type(path_container)!r}"
            )
    elif container == "array":
        if not isinstance(path_container, Sequence):
            raise PatchApplicationError(
                f"expected array container at {path!r}, got {type(path_container)!r}"
            )

    # mutability constraint
    if mutable is not None:
        is_mutable = isinstance(path_container, (MutableMapping, MutableSequence))
        if is_mutable is not mutable:
            if mutable:
                raise PatchApplicationError(
                    f"expected mutable container at {path!r}, got {type(path_container)!r}"
                )
            raise PatchApplicationError(
                f"expected immutable container at {path!r}, got {type(path_container)!r}"
            )

    # existence constraint
    try:
        path_container[path_key]
    except (KeyError, IndexError, TypeError) as e:
        # Missing key, index out of bounds, or invalid "-" access.
        if exists:
            raise PatchApplicationError(f"target at {path!r} does not exist") from e
    else:
        if exists is False:
            raise PatchApplicationError(f"target at {path!r} already exists")

    return path_container, path_key


def assert_valid(doc: JSONValue, *paths: JSONPointer[Any]) -> None:
    """
    Assert that pointers are resolvable against the document structure.

    Root pointers are allowed and treated as valid.
    """
    for path in paths:
        if not is_root(path):
            resolve_last(doc, path)


def assert_targets(
    doc: JSONValue,
    *paths: JSONPointer[Any],
    exists: bool | None = None,
    mutable: bool | None = None,
) -> None:
    """
    Assert invariants about multiple target locations.

    Root pointers are allowed; they are considered to exist and be writable.
    """
    for path in paths:
        if not is_root(path):
            resolve_last(doc, path, exists=exists, mutable=mutable)


def is_parent_path(
    *, parent_path: JSONPointer[Any], child_path: JSONPointer[Any]
) -> bool:
    """
    Return True if `parent_path` is a strict parent of `child_path`.

    Root is treated as a parent of all paths.
    """
    # Fail fast if malformed pointer
    parent_ptr, child_ptr = cast_to_pointer(parent_path), cast_to_pointer(child_path)

    # Strict parentage only
    if parent_path == child_path:
        return False

    # Due to a bug in the upstream `jsonpointer` library, where jp1.contains(root_pointer)`
    # is always False, we special-case root:
    if is_root(parent_path):
        return True

    return child_ptr.contains(parent_ptr)  # type: ignore[no-any-return]


def get(doc: JSONValue, path: JSONPointer[U]) -> U:
    """
    Return the value at `path`, validated against the pointer's type parameter `U`.
    """
    if is_root(path):
        value = doc
    else:
        container, key = resolve_last(doc, path, exists=True)
        value = container[key]  # type: ignore[index]
    return path.validate_pointed_value(value)


def add(doc: JSONValue, path: JSONPointer[Any], value: JSONValue) -> JSONValue:
    """
    RFC 6902 `add` semantics.

    - Root replaces the entire document.
    - Object key assigns.
    - Array index inserts; "-" appends.
    """
    if is_root(path):
        return value

    container, key = resolve_last(doc, path, mutable=True)

    if isinstance(container, MutableMapping):
        container[key] = value  # type: ignore[index]
    elif isinstance(container, MutableSequence):
        if key == "-":
            key = len(container)
        if key > len(container):  # type: ignore[operator]
            raise PatchApplicationError(f"target at {path!r} is out of range")
        assert key >= 0, "JsonPointer implementation changed"  # type: ignore[operator]
        container.insert(key, value)  # type: ignore[arg-type]

    return doc


def remove(doc: JSONValue, path: JSONPointer[Any]) -> JSONValue:
    """RFC 6902 `remove` semantics. Removing root is forbidden."""
    if is_root(path):
        raise PatchApplicationError("cannot remove the root")
    container, key = resolve_last(doc, path, exists=True, mutable=True)
    del container[key]  # type: ignore[arg-type]
    return doc


def replace(doc: JSONValue, path: JSONPointer[Any], value: JSONValue) -> JSONValue:
    """RFC 6902 `replace` semantics. Root replaces the entire document."""
    if is_root(path):
        return value
    doc2 = remove(doc, path)
    return add(doc2, path, value)


def move(
    doc: JSONValue, from_path: JSONPointer[Any], to_path: JSONPointer[Any]
) -> JSONValue:
    """RFC 6902 `move` semantics with a guard against moving into a descendant."""
    assert_targets(doc, from_path, exists=True, mutable=True)
    if from_path == to_path:
        return doc
    if is_root(to_path):
        return get(doc, from_path)

    if is_parent_path(parent_path=from_path, child_path=to_path):
        raise PatchApplicationError(
            f"path {from_path!r} cannot be moved into its child path {to_path!r}"
        )

    value = get(doc, from_path)
    doc2 = remove(doc, from_path)
    return add(doc2, to_path, value)


def copy(
    doc: JSONValue, from_path: JSONPointer[Any], to_path: JSONPointer[Any]
) -> JSONValue:
    """RFC 6902 `copy` semantics."""
    value = get(doc, from_path)
    if from_path == to_path:
        return doc
    return add(doc, to_path, deepcopy(value))


def test(doc: JSONValue, path: JSONPointer[Any], expected: JSONValue) -> JSONValue:
    """
    RFC 6902 `test` semantics using JSON-ish equality.

    Raises TestOpFailed on failure; returns `doc` unchanged on success.
    """
    value = get(doc, path)
    if not are_equal(value, expected):
        raise TestOpFailed(
            f"test at path {path!r} failed, got {value!r} but expected {expected!r}"
        )
    return doc


def swap(
    doc: JSONValue,
    first_path: JSONPointer[JSONValue],
    second_path: JSONPointer[JSONValue],
) -> JSONValue:
    """
    Swap the values at `first_path` and `second_path`.

    - Both paths must exist and be mutable.
    - Swapping a path with one of its own descendants is forbidden and
      raises PatchApplicationError.

    This is a non-standard convenience primitive that can be used as a
    building block for more complex custom operations.

    The document is mutated in place and returned for convenience.
    """
    assert_targets(doc, first_path, second_path, exists=True, mutable=True)
    if first_path == second_path:
        return doc  # no-op

    # Disallow nested swaps (parent <-> child)
    for parent, child in ((first_path, second_path), (second_path, first_path)):
        if is_parent_path(parent_path=parent, child_path=child):
            raise PatchApplicationError(
                f"path {parent!r} cannot be moved into its child path {child!r}"
            )

    first_path_value = get(doc, first_path)
    doc_intermediate = move(doc, second_path, first_path)
    return add(doc_intermediate, second_path, first_path_value)


def transform(
    doc: JSONValue,
    path: JSONPointer[JSONValue],
    func: Callable[[T], T],
    *,
    expect_type: type[T]
    | tuple[type, ...]
    | None = None,  # TODO: isinstance is incompatible with type aliases for now... https://discuss.python.org/t/type-aliases-dont-work-with-isinstance/104339
) -> JSONValue:
    """
    Read, transform, and write back the value at `path`.

    This is a general-purpose helper to make custom operations very small and
    declarative:

    1. Retrieve the current value at `path` with :func:`get`.
    2. Optionally enforce that it is an instance of `expect_type`.
    3. Call `func(current)` to obtain a new value.
    4. Write the new value back at `path` via :func:`replace`.

    Example - increment a numeric counter::

        doc = transform(doc, "/counter", lambda v: v + 1, expect_type=int)

    Example - toggle a boolean flag::

        doc = transform(doc, "/enabled", lambda v: not v, expect_type=bool)

    The document is mutated in place and returned for convenience.
    """
    current = get(doc, path)

    if expect_type is not None and not isinstance(current, expect_type):
        raise PatchApplicationError(
            f"expected value of type {expect_type!r} at {path!r}, got {type(current)!r}"
        )

    new_value = func(current)  # type: ignore[arg-type]
    return replace(doc, path, new_value)


def append(
    doc: JSONValue,
    path: JSONPointer[JSONValue],
    value: JSONValue,
) -> JSONValue:
    """
    Append `value` to the end of the array located at `path`.

    Unlike RFC 6902 `add` (which treats the pointer as an insertion *position*),
    this helper treats `path` as the location of the array itself:

      - `path` must resolve to a JSONArray.
      - `value` then appended to that array.

    This is intended as a convenience for custom operations, not as a strict
    encoding of RFC 6902, and is useful for LLM-friendly "append" semantics.

    The document is mutated in place and returned for convenience.
    """
    target = get(doc, path)
    if not isinstance(target, MutableSequence):
        raise PatchApplicationError(
            f"append expects an array at {path!r}, got {type(target)!r}"
        )
    target.insert(len(target), value)
    return doc


def extend(
    doc: JSONValue,
    path: JSONPointer[JSONValue],
    values: Sequence[JSONValue],
) -> JSONValue:
    """
    Extend the array located at `path` with each element of `values`.

    - `path` must resolve to a JSONArray value.
    - Each element from `values` is appended in order to that array.

    As with :func:`append`, this helper treats `path` as pointing to the array
    itself, not to an insertion index, and is intended for custom operations
    that want "push many" semantics.

    The document is mutated in place and returned for convenience.
    """
    target = get(doc, path)
    if not isinstance(target, MutableSequence):
        raise PatchApplicationError(
            f"extend expects an array at {path!r}, got {type(target)!r}"
        )
    target.extend(values)
    return doc


# TODO: update for JSONObject


def toggle_bool(doc: JSONValue, path: JSONPointer[JSONValue]) -> JSONValue:
    """
    Toggle a boolean value at `path`.

    - The value at `path` must be a `JSONBoolean` (not merely truthy/falsy).
    - The value is replaced with `not current`.

    This can be useful for interactive/LLM-driven workflows where
    "toggle this flag" is more natural than "replace with true/false".

    The document is mutated in place and returned for convenience.
    """
    current = get(doc, path)
    if not isinstance(current, bool):
        raise PatchApplicationError(
            f"toggle_bool expects a boolean at {path!r}, got {type(current)!r}"
        )
    return replace(doc, path, not current)


def increment_number(
    doc: JSONValue,
    path: JSONPointer[JSONValue],
    amount: JSONNumber = 1,
) -> JSONValue:
    """
    Increment a numeric value at `path` by `amount`.

    - The current value must be a `JSONNumber`.
    - `amount` must also be a `JSONNumber`.

    The document is mutated in place and returned for convenience.
    """
    current = get(doc, path)
    if not isinstance(current, (int, float)) or isinstance(current, bool):
        raise PatchApplicationError(
            f"increment_number expects a numeric value at {path!r}, got {type(current)!r}"
        )
    return replace(doc, path, current + amount)


def decrement_number(
    doc: JSONValue,
    path: JSONPointer[JSONValue],
    amount: JSONNumber = 1,
) -> JSONValue:
    """
    Decrement a numeric value at `path` by `amount`.

    - The current value must be a `JSONNumber`.
    - `amount` must also be a `JSONNumber`.

    The document is mutated in place and returned for convenience.
    """
    current = get(doc, path)
    if not isinstance(current, (int, float)) or isinstance(current, bool):
        raise PatchApplicationError(
            f"decrement_number expects a numeric value at {path!r}, got {type(current)!r}"
        )
    return replace(doc, path, current - amount)


def transform_n(
    doc: JSONValue,
    *,
    inputs: Sequence[JSONPointer[Any]],
    outputs: Sequence[JSONPointer[Any]],
    func: Callable[..., Any],
) -> JSONValue:
    """
    N-ary transform using typed pointers.

    Reads values at `inputs`, validates each value using the pointer's type parameter,
    calls `func(*values)`, then writes the result(s) to `outputs` (after validating
    each result against the corresponding output pointer's type parameter).

    Return shape rules:
      - If len(outputs) == 1: func may return a single value (scalar).
      - If len(outputs) > 1: func must return a tuple/list of that length.
    """
    if not (inputs or outputs):
        raise ValueError("inputs and outputs must be nonempy")

    # Read + validate inputs
    in_values: list[Any] = []
    for p in inputs:
        raw = get(doc, p)
        in_values.append(p.validate_pointed_value(raw))

    # validate output paths
    for p in outputs:
        raw = get(doc, p)
        p.validate_pointed_value(raw)

    # Apply transform function
    result = func(*in_values)

    # Normalize output values
    if len(outputs) == 1:
        out_values = (result,)
    else:
        if not isinstance(result, (tuple, list)):
            raise PatchApplicationError(
                f"transform_n expected {len(outputs)} return values, got scalar {result!r}"
            )
        if len(result) != len(outputs):
            raise PatchApplicationError(
                f"transform_n expected {len(outputs)} return values, got {len(result)}"
            )
        out_values = tuple(result)

    # Validate + write outputs
    for p, v in zip(outputs, out_values):
        # v = p.validate_pointed_value(v)  # validate output type too? would be confusing. I think only let the generic refer to existing target, not desired target.
        doc = replace(doc, p, v)

    return doc


transform_n(
    4,
    inputs=[JSONPointer[JSONNumber]("/foo")],
    outputs=[JSONPointer("/bar")],
    func=lambda x: x + 1,
)
