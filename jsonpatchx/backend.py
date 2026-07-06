import re
from abc import abstractmethod
from collections.abc import Iterable, Sequence
from enum import Enum, auto
from typing import (
    Protocol,
    Self,
    assert_never,
    cast,
    override,
    runtime_checkable,
)

from jsonpath import JSONPathEnvironment
from jsonpointer import JsonPointer  # type: ignore[import-untyped]
from jsonpointer import JsonPointerException as JPException

from jsonpatchx.exceptions import InvalidJSONPointer, InvalidJSONSelector
from jsonpatchx.types import JSONValue, _is_array, _is_container, _is_object

# strict RFC 6901 array index
_NONNEGATIVE_ARRAY_INDEX_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")
# integer array index (negative allowed)
_INTEGER_ARRAY_INDEX_PATTERN = re.compile(r"^-?(0|[1-9][0-9]*)$")


class _FixedJsonPointer(JsonPointer):  # type: ignore[misc]
    # fixes https://github.com/stefankoegl/python-json-pointer/issues/70
    @override
    @classmethod
    def get_part(cls, doc, part):  # type: ignore[no-untyped-def]
        """Resolve one pointer token against a container.

        Arguments:
            doc: Container currently being traversed.
            part: Raw pointer token to resolve.

        Returns:
            The normalized key or index for `part`.

        Raises:
            JPException: If `doc` is a string and cannot be traversed further.
        """
        if isinstance(doc, str):
            raise JPException(
                f"Cannot apply token {part!r} to non-container type {type(doc)}"
            )
        key = super().get_part(doc, part)
        return key

    @override
    def walk(self, doc, part):  # type: ignore[no-untyped-def]
        """Resolve and traverse one pointer token.

        Arguments:
            doc: Container currently being traversed.
            part: Raw pointer token to traverse.

        Returns:
            The child value reached by `part`.
        """
        part = self.get_part(doc, part)  # type: ignore[no-untyped-call]
        return super().walk(doc, part)


@runtime_checkable
class PointerBackend(Protocol):
    """
    Protocol for pointer implementations used by `JSONPointer`.

    A pointer backend parses a pointer string, exposes unescaped `parts`,
    reconstructs itself from those parts, resolves against a JSON document, and
    round-trips through `str()`.

    Required Invariants:
        - `str(type(ptr)(str(ptr))) == str(ptr)`
        - `str(type(ptr).from_parts(ptr.parts)) == str(ptr)`

        Backends define their own syntax and root representation. Higher-level
        JsonPatchX APIs normalize backend-raised errors, and backend instances
        should be safe to reuse across calls.
    """

    @abstractmethod
    def __init__(self, pointer: str) -> None:
        """Parse a backend-specific pointer string.

        Arguments:
            pointer: A string in the backend's syntax.
        """

    @property
    @abstractmethod
    def parts(self) -> Sequence[str]:
        """The pointer's unescaped parts in traversal order."""

    @classmethod
    @abstractmethod
    def from_parts(cls, parts: Iterable[str]) -> Self:
        """Build a pointer from unescaped parts.

        Arguments:
            parts: Unescaped pointer parts in traversal order.

        Returns:
            pointer: A pointer equivalent to those parts.
        """

    @abstractmethod
    def resolve(self, doc: JSONValue) -> JSONValue:
        """Resolve this pointer against a JSON document.

        Arguments:
            doc: JSON document to resolve against.

        Returns:
            The value targeted by the pointer.
        """

    @override
    @abstractmethod
    def __str__(self) -> str:
        """The canonical string representation of this pointer."""


class DEFAULT_POINTER_CLS:
    """
    Default JSON Pointer backend powered by `jsonpointer.JsonPointer`.

    This implementation parses RFC 6901 pointer strings, exposes unescaped
    parts, reconstructs canonical pointers from parts, and resolves pointers
    against JSON documents.
    """

    __slots__ = ("_parts", "_pointer")

    @override
    def __init__(self, pointer: str) -> None:
        """Parse an RFC 6901 JSON Pointer string.

        Arguments:
            pointer: A string in RFC 6901 syntax. `/` and `~` inside tokens
                must be escaped as `~1` and `~0` respectively.

        Example:
            ```python
            DEFAULT_POINTER_CLS("/foo/bar~1baz/~0qux")
            ```
        """
        self._pointer = _FixedJsonPointer(pointer)
        self._parts = cast(Sequence[str], self._pointer.parts)

    @property
    def parts(self) -> Sequence[str]:
        """The pointer's unescaped RFC 6901 reference tokens in traversal order.

        RFC 6901 escapes `/` as `~1` and `~` as `~0` inside tokens. `parts`
        returns the decoded values.

        Example:
            ```python
            ptr = DEFAULT_POINTER_CLS("/foo/bar~1baz/~0qux")
            ptr.parts  # ("foo", "bar/baz", "~qux")
            ```
        """
        return self._parts

    @classmethod
    def from_parts(cls, parts: Iterable[str]) -> Self:
        """Build an RFC 6901 pointer from unescaped reference tokens.

        Arguments:
            parts: Unescaped RFC 6901 reference tokens.

        Returns:
            pointer: A canonical RFC 6901 pointer for those tokens.

        Example:
            ```python
            DEFAULT_POINTER_CLS.from_parts(["foo", "bar/baz", "~qux"])
            # DEFAULT_POINTER_CLS("/foo/bar~1baz/~0qux")
            ```
        """
        canonical = _FixedJsonPointer.from_parts(parts)
        return cls(str(canonical))

    def resolve(self, doc: JSONValue) -> JSONValue:
        """Resolve this pointer against a JSON document.

        Arguments:
            doc: JSON document to resolve against.

        Returns:
            The value targeted by this pointer.

        Example:
            ```python
            ptr = DEFAULT_POINTER_CLS("/users/0/name")
            ptr.resolve({"users": [{"name": "Alice"}]})  # "Alice"
            ```
        """
        return cast(JSONValue, self._pointer.resolve(doc))

    @override
    def __str__(self) -> str:
        """The canonical RFC 6901 JSON Pointer string, with tokens re-escaped.

        Example:
            ```python
            ptr = DEFAULT_POINTER_CLS.from_parts(["foo", "bar/baz", "~qux"])
            str(ptr)  # "/foo/bar~1baz/~0qux"
            ```
        """
        return str(self._pointer)

    @override
    def __repr__(self) -> str:
        return "JsonPointerRFC6901(" + repr(self._pointer.path) + ")"


def _is_root_ptr(ptr: PointerBackend, doc: JSONValue) -> bool:
    """
    Check whether this pointer backend's target is the root.

    Arguments:
        ptr: Pointer to test.
        doc: JSON document to resolve against.

    Returns:
        `True` if `ptr` resolves to `doc` itself, else `False`.

    Notes:
        Custom backends are not required to accept `""` as the root, nor are
        they required to have exactly one root representation.
    """
    try:
        target = ptr.resolve(doc)
    except Exception:
        return False
    return doc == target


def _parent_ptr_of[PB: PointerBackend](ptr: PB) -> PB:
    """Build the parent pointer.

    Arguments:
        ptr: Pointer whose parent should be returned.

    Returns:
        A pointer to the parent location.

    Notes:
        This reconstructs the parent from `ptr.parts[:-1]`. Backends that want
        to cache parent information can still expose that through their own
        implementation details.
    """
    # NOTE: potentially check if ptr.parent property exists, if they want to cache it for example
    return ptr.from_parts(ptr.parts[:-1])


def _pointer_backend_instance[PB: PointerBackend](
    path: str, *, pointer_cls: type[PB]
) -> PB:
    """
    Internal: construct a PointerBackend instance for a path string.

    Arguments:
        path: Pointer string to parse.
        pointer_cls: Backend class used to parse the pointer. Callers are
            responsible for ensuring this is a concrete, non-abstract class;
            `JSONPointer._validate_backend_arg` is the single canonical
            place that enforces this, for every path that reaches a backend
            class (a direct argument, a schema-build-time argument, or a
            `TypeVar` default), before one ever reaches this function.

    Returns:
        A backend instance for `path`.

    Raises:
        TypeError: If the constructor raises `TypeError`, or the constructor
            returns an object that does not implement `PointerBackend`.
        InvalidJSONPointer: If the backend constructor raises a non-`TypeError`
            exception (path string is invalid for the given backend).
    """
    try:
        ptr = pointer_cls(path)
    except TypeError as e:
        raise TypeError(
            f"pointer_cls {pointer_cls!r} is not a usable PointerBackend: {e}"
        ) from e
    except Exception as e:
        if (
            pointer_cls is DEFAULT_POINTER_CLS
        ):  # the string is not valid jsonpointer syntax
            raise InvalidJSONPointer(f"invalid RFC6901 JSON Pointer: {path!r}") from e
        else:  # the string and class are incompatible
            raise InvalidJSONPointer(
                f"invalid JSON Pointer for {pointer_cls!r}: {path!r}"
            ) from e

    if not isinstance(ptr, PointerBackend):
        raise TypeError(
            f"pointer_cls {pointer_cls!r} instances must implement the PointerBackend Protocol"
        )
    return ptr


# NOTE: move methods that raise InvalidJSONPointer below


# Backend resolution helpers


class TargetState(Enum):
    """Return type of `classify_state`, describing how a pointer relates to a specific location in a document."""

    ROOT = auto()
    """The pointer targets the document root."""
    PARENT_NOT_FOUND = auto()
    """A parent pointer segment could not be resolved."""
    PARENT_NOT_CONTAINER = auto()
    """The parent resolved, but is neither an object nor an array."""
    OBJECT_KEY_MISSING = auto()
    """The parent is an object, and the final key is not present."""
    ARRAY_KEY_INVALID = auto()
    """The parent is an array, and the final token is not a valid array index or append token."""
    ARRAY_INDEX_OUT_OF_RANGE = auto()
    """The parent is an array, and the numeric index is outside the accepted range."""
    ARRAY_INDEX_AT_END = auto()
    """The parent is an array, and the numeric index is exactly `len(array)`."""
    ARRAY_INDEX_APPEND = auto()
    """The parent is an array, and the final token is `"-"`."""
    VALUE_PRESENT = auto()
    """The pointer names an existing value."""
    VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX = auto()
    """The pointer names an existing array element through a negative index."""


def classify_state(ptr: PointerBackend, doc: JSONValue) -> TargetState:
    """
    Classify how a pointer relates to a document without mutating it.

    Useful for determining the applicability of an operation before attempting
    to apply it, and for generating informative error messages on failure.

    Arguments:
        ptr: Pointer to classify.
        doc: JSON document to classify the pointer against.

    Returns:
        The resolution state that best describes how `ptr` relates to `doc`.

    Example:
        ```python
        >>> doc = {"items": [1, 2, 3]}
        >>> classify_state(DEFAULT_POINTER_CLS("/items/1"), doc)
        TargetState.VALUE_PRESENT
        >>> classify_state(DEFAULT_POINTER_CLS("/items/9"), doc)
        TargetState.ARRAY_INDEX_OUT_OF_RANGE
        >>> classify_state(DEFAULT_POINTER_CLS("/missing"), doc)
        TargetState.OBJECT_KEY_MISSING
        ```
    """
    if _is_root_ptr(ptr, doc):
        return TargetState.ROOT

    try:
        parent_ptr = _parent_ptr_of(ptr)
        container = parent_ptr.resolve(doc)
        token = ptr.parts[-1]
    except Exception:
        return TargetState.PARENT_NOT_FOUND  # resolution failed to complete
    if not _is_container(container):
        return TargetState.PARENT_NOT_CONTAINER

    if _is_object(container):
        key = token
        if key not in container:
            return TargetState.OBJECT_KEY_MISSING
        return TargetState.VALUE_PRESENT

    elif _is_array(container):
        if token == "-":
            return TargetState.ARRAY_INDEX_APPEND
        if _INTEGER_ARRAY_INDEX_PATTERN.fullmatch(token):
            index = int(token)
            if index > len(container) or index < -len(container):
                return TargetState.ARRAY_INDEX_OUT_OF_RANGE
            if index == len(container):
                return TargetState.ARRAY_INDEX_AT_END
            if index < 0:
                return TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX
            return TargetState.VALUE_PRESENT
        return TargetState.ARRAY_KEY_INVALID

    else:  # pragma: no cover
        assert_never(container)


# -- JSONSelector Backend --


@runtime_checkable
class SelectorBackend(Protocol):
    """
    Protocol for custom query selector backends.

    A selector backend is the query analogue of `PointerBackend`: it parses a
    selector string and can iterate exact matched pointers against a JSON
    document.

    Required invariants:
        - `str(type(sel)(str(sel))) == str(sel)`
    """

    @abstractmethod
    def __init__(self, selector: str) -> None:
        """Parse a backend-specific selector string.

        Arguments:
            selector: A string in the backend's syntax.
        """

    @abstractmethod
    def pointers(self, doc: JSONValue) -> Iterable[PointerBackend]:
        """The pointers this selector matches against a JSON document.

        Arguments:
            doc: JSON document to match against.

        Returns:
            pointers: The backend-specific pointers matched by this selector.
        """

    @abstractmethod
    @override
    def __str__(self) -> str:
        """The canonical string representation of this selector."""


# Out of the box, JsonPatchX's default JSONPath backend follows upstream
# python-jsonpath's RFC 9535 path only if the jsonpatchx[strict-jsonpath]
# extra is installed. That extra pulls in python-jsonpath[strict], whose
# iregexp-check dependency segfaults on import under free-threaded Python.
# There is no PEP 508 marker that can express "not a free-threaded build" of
# a given Python version, so this cannot be enforced automatically: install
# jsonpatchx[strict-jsonpath] only on a standard (GIL) interpreter, never on
# a free-threaded one (3.13t, 3.14t, ...).
#
# Without jsonpatchx[strict-jsonpath] (the default), JsonPatchX still uses
# JSONPathEnvironment(strict=True), so this only affects regex compliance:
# - match() and search() use Python's built-in re instead of the third-party
#   regex engine.
# - regex patterns are not validated against RFC 9485 I-Regexp.
#
# Clients can still use python-jsonpath directly with their own environment
# settings, or bind a custom selector backend in JsonPatchX. They just cannot
# change the fixed environment behind DEFAULT_SELECTOR_CLS itself.
_DEFAULT_SELECTOR_ENV = JSONPathEnvironment(strict=True)


class DEFAULT_SELECTOR_CLS:
    """
    Default JSONPath selector backend powered by `python-jsonpath`.

    This implementation compiles JSONPath expressions with the shared strict
    environment and yields exact pointer locations for each match.

    Disclaimer:
        This backend follows RFC 9535 path syntax and semantics only if the
        `jsonpatchx[strict-jsonpath]` extra is installed; otherwise
        regex-related behavior falls back to Python's built-in `re` module.
        Do not install `jsonpatchx[strict-jsonpath]` on a free-threaded Python
        build: its upstream `iregexp-check` dependency segfaults on import
        there, and no PEP 508 marker can select a standard build over a
        free-threaded build of the same Python version to guard against it
        automatically.
    """

    __slots__ = ("_path", "_selector")

    def __init__(self, selector: str) -> None:
        """Parse an RFC 9535 JSONPath selector string.

        Arguments:
            selector: A string in RFC 9535 syntax.
        """
        self._path = selector
        self._selector = _DEFAULT_SELECTOR_ENV.compile(selector)

    def pointers(self, doc: JSONValue) -> Iterable[DEFAULT_POINTER_CLS]:
        """The RFC 6901 JSON Pointers this JSONPath matches against a JSON document.

        Arguments:
            doc: JSON document to match against.

        Returns:
            pointers: The RFC 6901 JSON Pointers matched by this JSONPath.

        Example:
            ```python
            sel = DEFAULT_SELECTOR_CLS("$.users[*].name")
            doc = {"users": [{"name": "Alice"}, {"name": "Bob"}]}
            [str(p) for p in sel.pointers(doc)]  # ["/users/0/name", "/users/1/name"]
            ```
        """
        for match in self._selector.finditer(doc):
            yield DEFAULT_POINTER_CLS.from_parts((str(part) for part in match.parts))

    @override
    def __str__(self) -> str:
        """The canonical RFC 9535 JSONPath string."""
        return self._path

    @override
    def __repr__(self) -> str:
        return "JsonPathRFC9535(" + repr(self._path) + ")"


def _selector_backend_instance[SB: SelectorBackend](
    selector: str, *, selector_cls: type[SB]
) -> SB:
    """
    Internal: construct a SelectorBackend instance for a selector string.

    Arguments:
        selector: Selector string to parse.
        selector_cls: Backend class used to parse the selector. Callers are
            responsible for ensuring this is a concrete, non-abstract class;
            `JSONSelector._validate_backend_arg` is the single canonical
            place that enforces this, for every path that reaches
            a backend class (a direct argument, a schema-build-time
            argument, or a `TypeVar` default), before one ever reaches this
            function.

    Returns:
        A backend instance for `selector`.

    Raises:
        TypeError: If the constructor raises `TypeError`, or the constructor
            returns an object that does not implement `SelectorBackend`.
        InvalidJSONSelector: If the backend constructor raises a non-`TypeError`
            exception (selector string is invalid for the given backend).
    """
    try:
        compiled = selector_cls(selector)
    except TypeError as e:
        raise TypeError(
            f"selector_cls {selector_cls!r} is not a usable SelectorBackend: {e}"
        ) from e
    except Exception as e:
        if selector_cls is DEFAULT_SELECTOR_CLS:
            raise InvalidJSONSelector(
                f"invalid JSONPath selector for default backend: {selector!r}"
            ) from e
        raise InvalidJSONSelector(
            f"invalid JSON selector for {selector_cls!r}: {selector!r}"
        ) from e

    if not isinstance(compiled, SelectorBackend):
        raise TypeError(
            f"selector_cls {selector_cls!r} instances must implement the SelectorBackend protocol"
        )

    return compiled
