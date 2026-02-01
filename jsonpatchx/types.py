from __future__ import annotations

import re
from abc import abstractmethod
from collections.abc import Iterable, Sequence
from functools import lru_cache
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Callable,
    Protocol,
    Self,
    TypeGuard,
    override,
    runtime_checkable,
)

from jsonpointer import JsonPointer  # type: ignore[import-untyped]
from jsonpointer import JsonPointerException as JPException
from pydantic import Field, TypeAdapter
from typing_extensions import TypeForm

from jsonpatchx.exceptions import InvalidJSONPointer

# Pydantic-aware JSON type aliases

type JSONBoolean = Annotated[bool, Field(strict=True, title="JSON boolean")]
type JSONNumber = Annotated[  # NOTE: document the necessity of field strictness. adapters strict too for preventing "2" -> 2 for JSONBoolean and int/float
    Annotated[int, Field(strict=True)]
    | Annotated[float, Field(strict=True, allow_inf_nan=False)],
    Field(
        title="JSON number",
        description="integer or finite float (no NaN/Infinity).",
    ),
]
type JSONString = Annotated[str, Field(strict=True, title="JSON string")]
type JSONNull = Annotated[None, Field(title="JSON null")]

type JSONArray[T] = Annotated[list[T], Field(strict=True, title="JSON array")]
type JSONObject[T] = Annotated[dict[str, T], Field(strict=True, title="JSON object")]
type JSONContainer[T] = JSONArray[T] | JSONObject[T]


def _is_container(value: JSONValue) -> TypeGuard[JSONContainer[JSONValue]]:
    """Internal: runtime check for JSON containers (dict/list)."""
    if isinstance(value, list):
        return True
    if isinstance(value, dict):
        return all(isinstance(k, str) for k in value)
    return False


type JSONValue = Annotated[
    JSONBoolean
    | JSONNumber
    | JSONString
    | JSONNull
    | JSONArray[JSONValue]
    | JSONObject[JSONValue],
    Field(title="JSON value"),
]  # NOTE: document somewhere tha you can't do isinstance because these are type aliases
"""
Pydantic-friendly type representing a strict JSON value.

Notes:
    - The standard JSON Patch operation schemas use it for ``value`` fields.
    - ``JSONPointer`` uses it as the document type for ``get``/``add``/``remove``.
    - Patch application helpers can optionally validate that inputs are legitimate JSON.
    - Containers are restricted to ``list`` and ``dict[str, ...]``.
    - Numeric values are restricted to ``int`` or finite ``float`` (no NaN/Infinity).
    - Pydantic validation is strict (no implicit coercions).
"""

# strict RFC 6901 array index
_NONNEGATIVE_ARRAY_INDEX_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")


# TypeAdapter helpers


@lru_cache(maxsize=512)
def _cached_type_adapter[T](expected: TypeForm[T]) -> TypeAdapter[T]:
    # https://docs.pydantic.dev/latest/concepts/performance/#typeadapter-instantiated-once
    return TypeAdapter(expected)


def _type_adapter_for[T](expected: TypeForm[T]) -> TypeAdapter[T]:
    """
    Internal: return a (usually cached) Pydantic TypeAdapter for a TypeForm.

    JSONPointer uses adapters at apply-time to validate that the resolved target
    conforms to the pointer's type parameter.

    Adapters are cached for performance when possible. Unhashable TypeForms are supported
    but cannot be cached.
    """
    try:
        try:
            return _cached_type_adapter(expected)  # type: ignore[arg-type]
        except TypeError:
            # Choice: Don't forbid unhashable typeforms, but don't break an arm supporting them either.
            # Why: Most TypeForms are hashable, even Annotated[int, json_schema_extra={"dict here": "still hashable"})].
            #      It's really just cases like Annotated[int, {"dict":"unhashable"}] that are too rare to support for now.
            return TypeAdapter(expected)
    except Exception as e:
        raise InvalidJSONPointer(
            f"Invalid type parameter for JSON Pointer: {expected!r}. Cannot create TypeAdapter. Did you implement __get_pydantic_core_schema__?"
        ) from e


_JSON_VALUE_ADAPTER: TypeAdapter[JSONValue] = _type_adapter_for(JSONValue)
# NOTE: not a huge fan of the pydantic error messages for simple cases like _JSON_VALUE_ADAPTER.python_validate({1:2})


# PointerBackend helpers

# You may be wondering, why does `_PointerClassProtocol` exist? Here's context.
#
# TL;DR: This library aims to surface user erros as eagerly as possible. It's not
#        possible to validate a custom pointer backend until it's instantiated. As
#        a workaround, `_PointerClassProtocol` exists internally to raise errors
#        at JSONPointer definition time, and `PointerBackend` exists inernally to
#        raise errors at JSONPointer instantiation time. Only `PointerBackend`
#        needs to be publicly exposed to communicate pointer backend requirements.
#
# `PointerBackend` is the public protocol for injecting custom pointer classes.
# `PointerBackend` is `@runtime_checkable` so that `OperationSchmea` can eagerly
# validate custom pointer classes. Unfortunately, though, it's invalid to do
# `issubclass(X, PointerBackend)` because of the following error:
#
#   TypeError: Protocols with non-method members don't support issubclass(). Non-method members: 'parts'.
#
# A workaround would be to use `isinstance` instead of `issubclass`, but that
# requires having a PointerBackend instance like `X("/foo/bar")`. The problem is
# that custom pointer backends are not required to use any particular syntax.
# This means it's not possible to know what strings are supposed to be valid
# for any given custom pointer backend. I considered requiring that all custom
# pointer backends accept the empty string, `""`, but it's not necessary.
# Instead, `_PointerClassProtocol` exists as an internal-only protocol just to
# be comptaible with `issubclass`. `PointerBackend` simply subclasses it and adds
# the instance-level requirements.


@runtime_checkable
class _PointerClassProtocol(Protocol):
    @abstractmethod
    def __init__(self, pointer: str) -> None:
        """Parse and construct a backend-specific pointer."""

    @classmethod
    @abstractmethod
    def from_parts(cls, parts: Iterable[str]) -> Self:
        """
        Construct a pointer from unescaped tokens.

        Implementations may accept tokens beyond strings (e.g. ints) and stringify them,
        but must preserve the invariant that ``from_parts(ptr.parts)`` round-trips.
        """

    @abstractmethod
    def resolve(self, data: Any) -> Any:
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

        Must round-trip such that ``PointerBackend(str(ptr))`` yields an equivalent pointer.
        """


@runtime_checkable
class PointerBackend(_PointerClassProtocol, Protocol):
    """
    Protocol for custom JSON Pointer backends.

    This library is pointer-backend agnostic. By default it uses ``jsonpointer.JsonPointer``,
    but advanced users may plug in a custom backend (different parsing or escaping rules, richer
    pointer objects, alternative traversal semantics, and so on).

    A backend only needs to provide a small pointer-shaped surface area:

    - Constructible from a pointer string.
    - Exposes unescaped path tokens via ``parts``.
    - Can be reconstructed from tokens via ``from_parts``.
    - Can resolve a pointer against a document via ``resolve``.
    - Has a round-trippable string form via ``__str__``.

    Notes:
        - The backend defines its own pointer syntax; there is no universal "root" string.
        - Round-trip invariants should hold for the backend's canonical string form:
          ``PointerBackend(x)`` equals ``PointerBackend(str(PointerBackend(x)))`` and
          ``PointerBackend(x)`` equals ``PointerBackend.from_parts(PointerBackend(x).parts)``.
        - The library may cache backend instances; implementations should be immutable or otherwise
          safe to reuse across calls.
        - Backends may raise whatever exceptions are natural for them. Higher-level APIs normalize
          backend failures into library patch errors for a consistent user experience.
    """

    @property
    @abstractmethod
    def parts(self) -> Sequence[str]:
        """Unescaped backend-specific tokens."""


@lru_cache(maxsize=512)
def _cached_json_pointer[P](path: str, *, pointer_cls: Callable[..., P]) -> P:
    """
    Internal: construct (and cache) a PointerBackend instance for a path string.

    Args:
        path: Pointer string to parse.
        pointer_cls: Backend class used to parse the pointer.

    Returns:
        A backend instance for ``path``.

    Raises:
        InvalidJSONPointer: If construction fails.
    """
    try:
        return pointer_cls(path)
    except Exception as e:
        if (
            pointer_cls is _DEFAULT_POINTER_CLS
        ):  # the string is not valid jsonpointer syntax
            raise InvalidJSONPointer(f"invalid JSON Pointer: {path!r}") from e
        else:  # the string and class are incompatible
            raise InvalidJSONPointer(
                f"invalid JSON Pointer for {pointer_cls!r}: {path!r}"
            ) from e


class _DEFAULT_POINTER_CLS(JsonPointer):  # type: ignore[misc]
    # fixes https://github.com/stefankoegl/python-json-pointer/issues/63
    @override
    @classmethod
    def get_part(cls, doc, part):  # type: ignore[no-untyped-def]
        key = super().get_part(doc, part)
        if isinstance(key, int) and not _NONNEGATIVE_ARRAY_INDEX_PATTERN.fullmatch(
            str(part)
        ):
            raise JPException("'%s' is not a valid sequence index" % part)
        return key

    @override
    def to_last(self, doc):  # type: ignore[no-untyped-def]
        doc, key = super().to_last(doc)
        if isinstance(key, int) and not _NONNEGATIVE_ARRAY_INDEX_PATTERN.fullmatch(
            str(self.parts[-1])
        ):
            raise JPException("'%s' is not a valid sequence index" % self.parts[-1])
        return doc, key

    @override
    def walk(self, doc, part):  # type: ignore[no-untyped-def]
        part = self.get_part(doc, part)  # type: ignore[no-untyped-call]
        return super().walk(doc, part)


if TYPE_CHECKING:
    _dont_raise_mypy_error_1: PointerBackend = _DEFAULT_POINTER_CLS("")
    from jsonpath import JSONPointer as ExtendedJsonPointer

    _dont_raise_mypy_error_2: PointerBackend = ExtendedJsonPointer("")
