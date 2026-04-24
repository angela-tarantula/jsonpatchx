import re
from abc import abstractmethod
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
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


@runtime_checkable
class PointerBackend(Protocol):
    """
    NOTE: also require that parent pointers are constructable from parts[:-1] OR require that in certain methods!
    Protocol for custom JSON Pointer backends.

    This library is pointer-backend agnostic. By default it uses `jsonpointer.JsonPointer`,
    but advanced users may plug in a custom backend (different parsing or escaping rules, richer
    pointer objects, alternative traversal semantics, and so on).

    A backend only needs to provide a small pointer-shaped surface area:

    - Constructible from a pointer string.
    - Exposes unescaped path tokens via `parts`.
    - Can be reconstructed from tokens via `from_parts`.
    - Can resolve a pointer against a document via `resolve`.
    - Has a round-trippable string form via `__str__`.

    Notes:
        - The backend defines its own pointer syntax; there is no universal "root" string.
        - Round-trip invariants should hold for the backend's canonical string form:
          `PointerBackend(x)` equals `PointerBackend(str(PointerBackend(x)))` and
          `PointerBackend(x)` equals `PointerBackend.from_parts(PointerBackend(x).parts)`.
        - The library may cache backend instances; implementations should be immutable or otherwise
          safe to reuse across calls.
        - Backends may raise whatever exceptions are natural for them. Higher-level APIs normalize
          backend failures into library patch errors for a consistent user experience.
    """

    @abstractmethod
    def __init__(self, pointer: str) -> None:
        """Parse and construct a backend-specific pointer."""

    @classmethod
    @abstractmethod
    def from_parts(cls, parts: Iterable[str]) -> Self:
        """
        Construct a pointer from unescaped tokens.

        Implementations may accept tokens beyond strings (e.g. ints) and stringify them,
        but must preserve the invariant that `from_parts(ptr.parts)` round-trips.
        """

    @abstractmethod
    def resolve(self, doc: JSONValue) -> JSONValue:
        """
        Resolve the pointer against a document using backend-defined traversal semantics.

        Implementations typically follow dict/list traversal rules, but the library
        does not require a particular exception type on failure.
        """

    @override
    @abstractmethod
    def __str__(self) -> str:
        """
        Return the backend's canonical string form (escaped tokens, if applicable).

        Must round-trip such that `PointerBackend(str(ptr))` yields an equivalent pointer.
        """

    @property
    @abstractmethod
    def parts(self) -> Sequence[str]:
        """Unescaped backend-specific tokens."""


class _DEFAULT_POINTER_CLS(JsonPointer):  # type: ignore[misc]
    # fixes https://github.com/stefankoegl/python-json-pointer/issues/70
    @override
    @classmethod
    def get_part(cls, doc, part):  # type: ignore[no-untyped-def]
        if isinstance(doc, str):
            raise JPException(
                f"Cannot apply token {part!r} to non-container type {type(doc)}"
            )
        key = super().get_part(doc, part)
        return key

    @override
    def walk(self, doc, part):  # type: ignore[no-untyped-def]
        part = self.get_part(doc, part)  # type: ignore[no-untyped-call]
        return super().walk(doc, part)

    @override
    def __repr__(self) -> str:
        return "JsonPointerRFC6901(" + repr(self.path) + ")"


def _is_root_ptr(ptr: PointerBackend, doc: JSONValue) -> bool:
    """
    Check whether this pointer backend's target is the root.

    Custom backends are not required to accept `""` as the root,
    nor are they required to have exclusively one reference to the root.
    """
    try:
        target = ptr.resolve(doc)
    except Exception:
        return False
    return doc == target


def _parent_ptr_of[PB: PointerBackend](ptr: PB) -> PB:
    """Get the parent pointer."""
    # NOTE: potentially check if ptr.parent property exists, if they want to cache it for example
    return ptr.from_parts(ptr.parts[:-1])


def _pointer_backend_instance[PB: PointerBackend](
    path: str, *, pointer_cls: type[PB]
) -> PB:
    """
    Internal: construct a PointerBackend instance for a path string.

    Arguments:
        path: Pointer string to parse.
        pointer_cls: Backend class used to parse the pointer.

    Returns:
        A backend instance for `path`.

    Raises:
        InvalidJSONPointer: If construction fails.
    """
    try:
        ptr = pointer_cls(path)
    except Exception as e:
        if (
            pointer_cls is _DEFAULT_POINTER_CLS
        ):  # the string is not valid jsonpointer syntax
            raise InvalidJSONPointer(f"invalid RFC6901 JSON Pointer: {path!r}") from e
        else:  # the string and class are incompatible
            raise InvalidJSONPointer(
                f"invalid JSON Pointer for {pointer_cls!r}: {path!r}"
            ) from e

    if not isinstance(ptr, PointerBackend):
        raise InvalidJSONPointer(
            f"pointer_cls {pointer_cls!r} instances must implement the PointerBackend Protocol"
        )
    return ptr


# NOTE: move methods that raise InvalidJSONPointer below


# Backend resolution helpers


class TargetState(Enum):
    """
    Internal: classification of JSONPointer target resolution states.

    Only use when subclassing JSONPointer for custom stateful behaviors.
    """

    ROOT = auto()
    PARENT_NOT_FOUND = auto()
    PARENT_NOT_CONTAINER = auto()
    OBJECT_KEY_MISSING = auto()
    ARRAY_KEY_INVALID = auto()
    ARRAY_INDEX_OUT_OF_RANGE = auto()
    ARRAY_INDEX_AT_END = auto()
    ARRAY_INDEX_APPEND = auto()
    VALUE_PRESENT = auto()
    VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX = auto()


def classify_state(ptr: PointerBackend, doc: JSONValue) -> TargetState:
    """
    Internal: Classify the state of a JSONPointer resolution against a document.

    Only use when subclassing JSONPointer for custom stateful behaviors.
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
class SelectorMatch(Protocol):
    """
    Minimal match shape returned by `SelectorBackend.finditer()`.

    Selector-backed mutation works by turning each match into an exact pointer,
    then reusing the existing `JSONPointer` mutation rules.
    """

    @property
    @abstractmethod
    def obj(self) -> JSONValue:
        """Return the matched value."""

    @property
    @abstractmethod
    def parts(self) -> Sequence[int | str]:
        """Return the exact path parts for this match."""

    @abstractmethod
    def pointer(self) -> PointerBackend:
        """
        Return an exact-location pointer for this match.

        Backend authors should return a concrete pointer object that satisfies
        the `PointerBackend` protocol.
        """


@runtime_checkable
class SelectorBackend(Protocol):
    """
    Protocol for custom query selector backends.

    A selector backend is the query analogue of `PointerBackend`:
    it parses a selector string and can iterate exact matches against a JSON
    document.
    """

    @abstractmethod
    def __init__(self, selector: str) -> None:
        """Parse and construct a backend-specific selector."""

    @abstractmethod
    def finditer(self, doc: JSONValue) -> Iterable[SelectorMatch]:
        """Yield backend-specific matches against `doc`."""

    @abstractmethod
    @override
    def __str__(self) -> str:
        """Return the backend's canonical string form."""


# Out of the box, JsonPatchX's default JSONPath backend follows upstream
# python-jsonpath's RFC 9535 path.
#
# The exception is Python 3.14 and later, where the upstream iregexp-check
# dependency behind python-jsonpath[strict] is not yet compatible with
# free-threaded Python. JsonPatchX still uses JSONPathEnvironment(strict=True)
# there, so this only affects regex compliance:
# - match() and search() use Python's built-in re instead of the third-party
#   regex engine.
# - regex patterns are not validated against RFC 9485 I-Regexp.
#
# Clients can still use python-jsonpath directly with their own environment
# settings, or bind a custom selector backend in JsonPatchX. They just cannot
# change the fixed environment behind _DEFAULT_SELECTOR_CLS itself.
_DEFAULT_SELECTOR_ENV = JSONPathEnvironment(strict=True)


@dataclass(frozen=True, slots=True)
class _DEFAULT_SELECTOR_MATCH(SelectorMatch):
    """
    Thin wrapper around an upstream python-jsonpath match.

    The built-in selector backend uses upstream JSONPath matching, but it
    exports exact locations through JsonPatchX's default RFC 6901 pointer
    backend instead of upstream's non-standard JSONPointer extensions.
    """

    obj: JSONValue
    parts: tuple[int | str, ...]

    @override
    def pointer(self) -> PointerBackend:
        return cast(PointerBackend, _DEFAULT_POINTER_CLS.from_parts(self.parts))


class _DEFAULT_SELECTOR_CLS:
    """
    Default JSONPath selector backend powered by `python-jsonpath`.

    The wrapped selector is compiled from a string using the fixed shared
    `_DEFAULT_SELECTOR_ENV`. Out of the box, this follows upstream's RFC 9535
    path. On Python 3.14 and later, the upstream `iregexp-check` dependency
    behind `python-jsonpath[strict]` is not yet compatible with free-threaded
    Python, so only regex-related RFC behavior falls back.
    """

    __slots__ = ("_path", "_selector")

    def __init__(self, selector: str) -> None:
        self._path = selector
        self._selector = _DEFAULT_SELECTOR_ENV.compile(selector)

    def finditer(self, doc: JSONValue) -> Iterable[SelectorMatch]:
        for match in self._selector.finditer(doc):
            yield _DEFAULT_SELECTOR_MATCH(
                obj=cast(JSONValue, match.obj),
                parts=match.parts,
            )

    @override
    def __str__(self) -> str:
        return self._path

    @override
    def __repr__(self) -> str:
        return "JsonPathDefault(" + repr(self._path) + ")"


def _selector_backend_instance[SB: SelectorBackend](
    selector: str, *, selector_cls: type[SB]
) -> SB:
    """
    Internal: construct a SelectorBackend instance for a selector string.

    Arguments:
        selector: Selector string to parse.
        selector_cls: Backend class used to parse the selector.

    Returns:
        A backend instance for `selector`.

    Raises:
        InvalidJSONSelector: If construction fails.
    """
    try:
        compiled = selector_cls(selector)
    except Exception as e:
        if selector_cls is _DEFAULT_SELECTOR_CLS:
            raise InvalidJSONSelector(
                f"invalid JSONPath selector for default backend: {selector!r}"
            ) from e
        raise InvalidJSONSelector(
            f"invalid JSON selector for {selector_cls!r}: {selector!r}"
        ) from e

    if not isinstance(compiled, SelectorBackend):
        raise InvalidJSONSelector(
            f"selector_cls {selector_cls!r} instances must implement the SelectorBackend protocol"
        )

    return compiled
