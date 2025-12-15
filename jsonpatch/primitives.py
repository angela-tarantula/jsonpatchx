"""
Primitive helper functions for defining custom `apply()` methods on `OperationSchema`
implementations.

These helpers centralize the tricky, low-level JSON Pointer and container manipulation
logic so that custom operations can be implemented declaratively in terms of:

    - "get the value at this JSON Pointer"
    - "add/replace/remove at this JSON Pointer"
    - "move/copy between JSON Pointers"
    - "transform/swap/append/extend at this JSON Pointer"


Type-checker note
-----------------
Mypy is not yet advanced enough to narrow the union of tuples returned by
`resolve_last()`: https://github.com/python/mypy/issues/9791. For example, when
`resolve_last()` returns a `(container, key)` pair where `container` is a
`MutableMapping`, mypy cannot infer that `key` must be a `str`. Most of the
`type: ignore` comments in this module are workarounds for that false positive.
They avoid littering the implementation with `typing.cast` calls.


JsonPointer dependency
----------------------
The only `JsonPointer` operations this library relies on are:

    - `JsonPointer.to_last(doc)`  → `(container, key)`
    - `JsonPointer.contains(other_pointer)` → bool

This is deliberate: it minimizes tight coupling to any particular `jsonpointer`
implementation and makes it easy to support custom pointer classes that satisfy
a simple two-method protocol.

Also: one limitation of the upstream `jsonpointer` library is that it does not
accept negative indices for JSON arrays. Supporting that would require upstream
changes and is out of scope here.
"""

from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence
from copy import deepcopy
from functools import lru_cache
from typing import Callable, Literal, TypeVar, overload

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

T = TypeVar("T", bound=JSONValue)


def are_equal(
    first: JSONValue, second: JSONValue
) -> bool:  # TODO: just use orjson and compare strings?
    """
    Compare two JSON-like values for *semantic* equality.

    This defines equality according to JSON-ish rules rather than Python's
    default equality semantics:

      - Booleans are **not** considered equal to numbers
        (e.g. `True != 1` and `False != 0`).
      - Integers and floats are compared numerically (e.g. `1 == 1.0`).
      - Strings are compared by value.
      - `null` is equal only to `null`.
      - Mappings (dict-like objects) are compared by keys and values,
        regardless of their concrete class.
      - Sequences (list-like objects) are compared by length and elements,
        in order, regardless of their concrete class.
      - Comparison is recursive for nested structures.

    This is useful for the `test` operation, where users typically expect
    JSON semantics rather than Python's more permissive equality.
    """
    # Reject mismatched types for JSON primitives that would otherwise compare equal in Python.
    if isinstance(first, bool) or isinstance(second, bool):
        # Require both to be bool to compare them
        if type(first) is bool and type(second) is bool:  # noqa: E721
            return first == second
        return False

    # Numbers: both must be int/float (but not bool)
    if isinstance(first, (int, float)) and isinstance(second, (int, float)):
        return first == second

    # Strings and null
    if isinstance(first, str) and isinstance(second, str):
        return first == second
    if first is None and second is None:
        return True

    # Mapping types (e.g., dict, defaultdict, custom dict-like)
    if isinstance(first, Mapping) and isinstance(second, Mapping):
        if set(first.keys()) != set(second.keys()):
            return False
        # Recursive DFS comparison of values # TODO: consider iterative DFS to avoid stackoverflow
        return all(are_equal(first[k], second[k]) for k in first)

    # Sequence types (e.g., list, deque, custom list-like) but not str/bytes
    if (
        isinstance(first, Sequence)
        and isinstance(second, Sequence)
        and not isinstance(first, (str, bytes, bytearray))
        and not isinstance(second, (str, bytes, bytearray))
    ):
        if len(first) != len(second):
            return False
        # Recursive DFS comparison of values # TODO: consider iterative DFS to avoid stackoverflow
        return all(are_equal(a, b) for a, b in zip(first, second))

    return False


def is_root(path: JSONPointer) -> bool:
    """Return ``True`` if `path` points to the root (``""``), otherwise ``False``."""
    return path == ""


@lru_cache
def cast_to_pointer(path: JSONPointer) -> JsonPointer:
    """
    Convert a `JSONPointer` string into a `JsonPointer` instance.

    In normal usage this will be called on values that have already passed
    Pydantic validation. The error handling is defensive, so that even if a
    user bypasses validation and passes an invalid pointer, we still raise a
    well-typed :class:`PatchApplicationError`.
    """
    try:
        return JsonPointer(path)
    except JsonPointerException as e:
        raise PatchApplicationError(f"expected {path!r} to be a JSON Pointer") from e


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
    Resolve a JSON Pointer to its *parent container* and final token.

    This resolves `path` against `doc` and returns ``(container, key)`` such that:

    - ``container[key]`` refers to the value designated by ``path``.
    - ``container`` is either an object (mapping) or array (sequence).
    - ``key`` is:
        * a ``str`` when ``container`` is an object.
        * a non-negative ``int`` or the special string ``"-"`` when ``container`` is an array.

    This function *optionally* enforces additional invariants through keyword
    arguments, while still giving callers access to the raw container/key pair.

    Parameters
    ----------
    doc:
        JSON document to resolve against (assumed valid).
    path:
        JSON Pointer to resolve. Must not point to the root (there is no “parent”
        container to return).

    exists:
        Whether the *target* (i.e. ``container[key]``) is required to exist:

        - ``True``  -> the target must exist; a missing key / out-of-range index / illegal ``"-"`` access raises PatchApplicationError.
        - ``False`` -> the target must *not* exist; if it does, a PatchApplicationError is raised.
        - ``None``  -> no existence check is enforced (default).

    mutable:
        Whether the resolved container must be mutable:

        - ``True``  -> container must be a MutableMapping or MutableSequence.
        - ``False`` -> container must *not* be mutable.
        - ``None``  -> no mutability check is enforced (default).

    container:
        Optional constraint on the container type:

        - ``"object"`` -> container must be an object (mapping-like).
        - ``"array"``  -> container must be an array (sequence-like, non-string).
        - ``None``     -> no explicit container-type constraint (default).

    Returns
    -------
    (container, key):
        The resolved container and key/index for the target of ``path``. The
        combination is always suitable for use in:

        - ``value = container[key]``
        - ``container[key] = value``
        - ``del container[key]``

        subject to the requested invariants.

    Raises
    ------
    PatchApplicationError:
        If any of the requested invariants are violated, or if the pointer
        cannot be resolved.
    """
    if is_root(path):
        raise PatchApplicationError("tried to resolve a path to last, but got root")

    ptr = cast_to_pointer(path)

    try:
        path_container, path_key = ptr.to_last(doc)
        assert isinstance(path_container, (Mapping, Sequence)) and not isinstance(
            path_container, (str, bytes, bytearray)
        ), "JsonPointer implementation changed"
    except JsonPointerException as e:
        raise PatchApplicationError(f"unable to resolve path {path!r}: {e}") from e

    # Container-type constraint
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

    # Mutability constraint
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

    # Existence constraint
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


def assert_valid(doc: JSONValue, *paths: JSONPointer) -> None:
    """
    Assert that all provided pointers are syntactically valid and resolvable.

    This checks that each path:

    - is a valid JSON Pointer, and
    - can be resolved to a parent container and key via :func:`resolve_last`.

    It does *not* require that the target exists; it only validates that the
    pointer points somewhere sensible in the document structure.

    Unlike :func:`resolve_last`, it is root-friendly. Roots are considered valid.
    """
    for path in paths:
        if not is_root(path):
            resolve_last(doc, path)


def assert_targets(
    doc: JSONValue,
    *paths: JSONPointer,
    exists: bool | None = None,
    mutable: bool | None = None,
) -> None:
    """
    Assert invariants about a collection of target locations.

    This is a convenience wrapper over :func:`resolve_last` for multiple paths.
    For each path, it enforces:

    - `exists`: whether the target must or must not exist.
    - `mutable`: whether the container must be mutable or immutable.

    It is useful when a composite operation needs to ensure all of its inputs
    are valid before making any modifications.

    Unlike :func:`resolve_last`, it is root-friendly. Roots are considered to
    exist and be mutable.
    """
    for path in paths:
        if not is_root(path):
            resolve_last(doc, path, exists=exists, mutable=mutable)


def is_parent_path(*, parent_path: JSONPointer, child_path: JSONPointer) -> bool:
    """Return True if `parent_path` is a strict parent of `child_path`."""
    # Fail fast
    parent_ptr, child_ptr = cast_to_pointer(parent_path), cast_to_pointer(child_path)

    # Strict parentage only
    if parent_path == child_path:
        return False

    # Due to a bug in the upstream `jsonpointer` library, where jp1.contains(root_pointer)`
    # is always False for root, we special-case root:
    if is_root(parent_path):
        return True

    # jsonpointer is untyped, but this is the intended API
    return child_ptr.contains(parent_ptr)  # type: ignore[no-any-return]


def get(doc: JSONValue, path: JSONPointer) -> JSONValue:
    """
    Return the value at `path` within `doc`.

    Raises:
        PatchApplicationError:
            If the target location does not exist or the pointer cannot
            be resolved.
    """
    if is_root(path):
        return doc
    container, key = resolve_last(doc, path, exists=True)
    return container[key]  # type: ignore[index] # mypy is not advanced enough to narrow tuples


def add(doc: JSONValue, path: JSONPointer, value: JSONValue) -> JSONValue:
    """
    Add `value` at `path` within `doc` (RFC 6902 `add` semantics).

    - If `path` is root, the entire document is replaced with `value`.
    - Otherwise:
        * If the container is an object, ``container[key] = value``.
        * If the container is an array:
            - key ``"-"`` appends to the end.
            - an integer key in ``[0, len(array)]`` inserts at that index.
            - indices greater than ``len(array)`` raise PatchApplicationError.
        * Immutable containers also raise PatchApplicationError.

    The document is mutated in place and returned for convenience.
    """
    if is_root(path):
        return value  # replace root

    container, key = resolve_last(doc, path, mutable=True)

    if isinstance(container, MutableMapping):
        container[key] = value  # type: ignore[index] # mypy is not advanced enough to narrow tuples
    elif isinstance(container, MutableSequence):
        if key == "-":
            key = len(container)
        # at this point, key should be an int, but mypy can't narrow it
        if key > len(container):  # type: ignore[operator]
            raise PatchApplicationError(f"target at {path!r} is out of range")
        assert key >= 0, "JsonPointer implementation changed"  # type: ignore[operator]
        container.insert(key, value)  # type: ignore[arg-type]
    return doc


def remove(doc: JSONValue, path: JSONPointer) -> JSONValue:
    """
    Remove the value at `path` within `doc` (RFC 6902 `remove` semantics).

    - Removing the root is forbidden and raises PatchApplicationError.
    - The target location must exist and be mutable;
      otherwise PatchApplicationError is raised.

    The document is mutated in place and returned for convenience.
    """
    if is_root(path):
        raise PatchApplicationError("cannot remove the root")
    container, key = resolve_last(doc, path, exists=True, mutable=True)
    del container[key]  # type: ignore[arg-type]
    return doc


def replace(
    doc: JSONValue,
    path: JSONPointer,
    value: JSONValue,
) -> JSONValue:
    """
    Replace the value at `path` with `value` (RFC 6902 `replace` semantics).

    - If `path` is root, the entire document is replaced with `value`.
    - The target location must exist and be mutable, otherwise
      PatchApplicationError is raised.

    The document is mutated in place and returned for convenience.
    """
    if is_root(path):
        return value  # replace root
    doc_intermediate = remove(doc, path)
    return add(doc_intermediate, path, value)


def move(
    doc: JSONValue,
    from_path: JSONPointer,
    to_path: JSONPointer,
) -> JSONValue:
    """
    Move a value from `from_path` to `to_path` (RFC 6902 `move` semantics).

    Behavior:

    - Both `from_path` and `to_path` must be valid, and the source target
    must exist and be mutable.
    - If `to_path` is root, the entire document is replaced with the
    value at `from_path`
    - If `from_path` is a strict parent of `to_path`, a PatchApplicationError
    is raised to prevent moving a node into one of its own descendants.
    - Otherwise, the value at `from_path` is removed and then added at
    `to_path` with standard `add` semantics.

    The document is mutated in place and returned for convenience.
    """
    assert_targets(doc, from_path, exists=True, mutable=True)
    if from_path == to_path:
        return doc  # no-op
    if is_root(to_path):
        return get(doc, from_path)  # replace root

    # Nested move: moving into a child of itself is illegal
    if is_parent_path(parent_path=from_path, child_path=to_path):
        raise PatchApplicationError(
            f"path {from_path!r} cannot be moved into its child path {to_path!r}"
        )

    value = get(doc, from_path)
    doc_intermediate = remove(doc, from_path)
    return add(doc_intermediate, to_path, value)


def copy(
    doc: JSONValue,
    from_path: JSONPointer,
    to_path: JSONPointer,
) -> JSONValue:
    """
    Copy a value from `from_path` to `to_path` (RFC 6902 `copy` semantics).

    - The value at `from_path` is deep-copied and added at `to_path` using
      standard `add` semantics.
    - The source location is left unchanged.

    The document is mutated in place and returned for convenience.
    """
    value = get(doc, from_path)
    if from_path == to_path:
        return doc  # no-op
    value_copy = deepcopy(value)
    return add(doc, to_path, value_copy)


def test(doc: JSONValue, path: JSONPointer, expected: JSONValue) -> JSONValue:
    """
    Test that the value at `path` equals `expected` (RFC 6902 `test` semantics).

    - If the values are not equal, :class:`TestOpFailed` is raised.
    - On success, the original document is returned unchanged.

    This function is suitable both for standalone `test` operations and for
    building higher-level "assert-and-then-apply" operations.
    """
    value = get(doc, path)
    if not are_equal(value, expected):
        raise TestOpFailed(
            f"test at path {path!r} failed, got {value!r} but expected {expected!r}"
        )
    return doc


def swap(
    doc: JSONValue,
    first_path: JSONPointer,
    second_path: JSONPointer,
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
    path: JSONPointer,
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
    path: JSONPointer,
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
    path: JSONPointer,
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


def toggle_bool(doc: JSONValue, path: JSONPointer) -> JSONValue:
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
    path: JSONPointer,
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
    path: JSONPointer,
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
