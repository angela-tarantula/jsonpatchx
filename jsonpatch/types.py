from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from functools import lru_cache
from typing import (
    Annotated,
    Any,
    Final,
    Generic,
    Literal,
    Protocol,
    Self,
    TypeGuard,
    TypeVar,
    cast,
    final,
    get_args,
    override,
    runtime_checkable,
)

from annotated_types import Ge
from jsonpointer import JsonPointer  # type: ignore[import-untyped]
from pydantic import (
    Field,
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    TypeAdapter,
    ValidationInfo,
)
from pydantic_core import core_schema as cs
from typing_extensions import TypeForm

from jsonpatch.exceptions import (
    InvalidJSONPointer,
    PatchApplicationError,
)

# Core, Pydantic-aware JSON type aliases

type JSONBoolean = Annotated[bool, Field(strict=True)]
type JSONNumber = (
    Annotated[int, Field(strict=True)]
    | Annotated[float, Field(strict=True, allow_inf_nan=False)]
)
type JSONString = Annotated[str, Field(strict=True)]
type JSONNull = None
type JSONPrimitive = JSONBoolean | JSONNumber | JSONString | JSONNull

type JSONArray[T_co] = Annotated[list[T_co], Field(strict=True)]
type JSONObject[T_co] = Annotated[dict[str, T_co], Field(strict=True)]
type JSONContainer[T_co] = JSONArray[T_co] | JSONObject[T_co]

type JSONValue = Annotated[
    JSONPrimitive | JSONContainer[JSONValue],
    Field(description="JSON value (RFC-style primitives, list, dict)"),
]
"""
Pydantic-friendly type representing a strict JSON value.

Notes:
    - JSON Patch operation schemas use it for ``value`` fields.
    - ``JSONPointer`` uses it as the document type for ``get``/``set``/``delete``.
    - Patch application helpers can optionally validate that inputs are legitimate JSON.
    - Containers are restricted to ``list`` and ``dict[str, ...]``.
    - Numeric values are restricted to ``int`` or finite ``float`` (no NaN/Infinity).
    - Pydantic validation is strict (no implicit coercions).
"""


def _is_container(value: JSONValue) -> TypeGuard[JSONContainer[JSONValue]]:
    """Internal: runtime check for JSON containers (dict/list)."""
    return isinstance(value, (dict, list))


# Internal type hints

type _JSONArrayKey = Annotated[int, Ge(0)] | Literal["-"]
type _JSONObjectKey = str
type _JSONKey = _JSONArrayKey | _JSONObjectKey


@runtime_checkable
class PointerBackend(Protocol):
    """
    Protocol for custom JSON Pointer backends.

    This library is pointer-backend agnostic. By default it uses ``jsonpointer.JsonPointer``,
    but advanced users may plug in a custom backend (different parsing or escaping rules, richer
    pointer objects, alternative traversal semantics, and so on).

    A backend only needs to provide a small RFC 6901-shaped surface area:

    - Constructible from a pointer string.
    - Exposes unescaped path tokens via ``parts``.
    - Can be reconstructed from tokens via ``from_parts``.
    - Can resolve a pointer against a document via ``resolve``.
    - Has a round-trippable string form via ``__str__``.

    Notes:
        - Round-trip invariants should hold:
          ``PointerBackend(x)`` equals ``PointerBackend(str(PointerBackend(x)))`` and
          ``PointerBackend(x)`` equals ``PointerBackend.from_parts(PointerBackend(x).parts)``.
        - The library may cache backend instances; implementations should be immutable or otherwise
          safe to reuse across calls.
        - Backends may raise whatever exceptions are natural for them. Higher-level APIs normalize
          backend failures into library patch errors for a consistent user experience.
    """

    def __init__(self, pointer: str) -> None:
        """
        Parse and construct an RFC 6901 JSON Pointer.

        The empty string ``""`` MUST be accepted and represents the root pointer.
        """
        ...

    @property
    def parts(self) -> Sequence[str]:
        """Unescaped RFC 6901 tokens. The root pointer has an empty sequence of parts."""
        ...

    @classmethod
    def from_parts(cls, parts: Iterable[Any]) -> Self:
        """
        Construct a pointer from unescaped tokens.

        Implementations may accept tokens beyond strings (e.g. ints) and stringify them,
        but must preserve the invariant that ``from_parts(ptr.parts)`` round-trips.
        """
        ...

    def resolve(self, doc: Any) -> Any:
        """
        Resolve the pointer against a document using backend-defined traversal semantics.

        Implementations typically follow RFC 6901 traversal rules (dict keys / list indices),
        but the library does not require a particular exception type on failure.
        """
        ...

    @override
    def __str__(self) -> str:
        """
        Return the RFC 6901 string form (escaped tokens).

        Must round-trip such that ``PointerBackend(str(ptr))`` yields an equivalent pointer.
        """
        ...


_ARRAY_INDEX_PATTERN: re.Pattern[str] = re.compile(r"^(0|[1-9][0-9]*)$")


def _parse_JSONArray_key(array: JSONArray[JSONValue], key: str) -> _JSONArrayKey:
    """
    Internal: parse a JSON Pointer token as a list index or '-' append marker.

    This helper implements the JSON Patch array-index semantics used by the patch engine:
    - '-' indicates append
    - otherwise the token must be a base-10 non-negative integer
    - index may equal len(array) for append-like behavior (RFC 6902 add semantics)
    """
    assert isinstance(array, list), "internal error: _parse_JSONArray_key"
    if key == "-":
        return "-"
    if not _ARRAY_INDEX_PATTERN.fullmatch(key):
        raise PatchApplicationError(f"invalid array index: {key!r}")
    idx = int(key)
    if idx > len(array):
        raise PatchApplicationError(f"index out of range: {key!r}")
    return idx


def _parse_JSONContainer_key(
    container: JSONContainer[JSONValue], token: str
) -> _JSONKey:
    """
    Internal: interpret a JSON Pointer token as either a dict key or list index.

    - dict -> token is used as-is
    - list -> token is parsed as an array key (int or '-')
    """
    assert isinstance(container, (dict, list)), (
        "internal error: _parse_JSONContainer_key"
    )
    # NOTE: when type-checker type narrowing improves, refactor this method to return
    # tuple[JSONArray[JSONValue], _JSONArrayKey] | tuple[JSONObject[JSONValue], _JSONObjectKey].
    # Currently, type-checkers miss that specificity and coerce to tuple[JSONContainer[JSONValue], _JSONKey]
    if isinstance(container, dict):
        return token
    return _parse_JSONArray_key(container, token)


@lru_cache(maxsize=512)
def _cached_type_adapter[T](expected: TypeForm[T]) -> TypeAdapter[T]:
    # https://docs.pydantic.dev/latest/concepts/performance/#typeadapter-instantiated-once
    return TypeAdapter(expected)


@lru_cache(maxsize=512)
def _cached_json_pointer(
    path: str, *, pointer_cls: type[PointerBackend]
) -> PointerBackend:
    # a cache here too doesn't hurt, to be implementation-agnostic
    return pointer_cls(path)


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
            f"invalid type parameter for JSON Pointer: {expected!r}; did you implement __get_pydantic_core_schema__?"
        ) from e


_JSON_VALUE_ADAPTER: TypeAdapter[JSONValue] = _type_adapter_for(JSONValue)
# NOTE: not a huge fan of the pydantic error messages for simple cases like _JSON_VALUE_ADAPTER.python_validate({1:2})


def _json_pointer_for(
    path: str, *, pointer_cls: type[PointerBackend]
) -> PointerBackend:
    """
    Internal: construct (and cache) a PointerBackend instance for a path string.

    Args:
        path: Pointer string to parse.
        pointer_cls: Backend class used to parse the pointer.

    Returns:
        A backend instance for ``path``.

    Raises:
        InvalidJSONPointer: If construction fails or the backend does not satisfy the
            ``PointerBackend`` protocol.
    """
    try:
        pointer = _cached_json_pointer(path, pointer_cls=pointer_cls)
    except Exception as e:
        if pointer_cls is _DEFAULT_POINTER_CLS:
            raise InvalidJSONPointer(f"invalid JSON Pointer: {path!r}") from e
        else:
            raise InvalidJSONPointer(
                f"invalid JSON Pointer for {pointer_cls!r}: {path!r}"
            ) from e

    if not isinstance(pointer, PointerBackend):
        # fail fast on invalid PointerBackend, but remember isinstance(x, Protocol) only verifies attribute existence
        # NOTE: maybe also add an invariance checker for the __str__ and from_parts methods.
        # NOTE: Also consider a global PointerBackend verification as opposed to per-JSONPointer[T]-instance
        raise InvalidJSONPointer(
            f"pointer backend {pointer_cls.__name__} does not satisfy PointerBackend protocol"
        )
    return pointer


_Nothing = object()
# NOTE: maybe add pydantic_core.MISSING to JSONPointer.get() on failure

_POINTER_BACKEND_CTX_KEY: Final[Literal["jsonpatch:pointer_backend"]] = (
    "jsonpatch:pointer_backend"
)
_DEFAULT_POINTER_CLS: Final[type[PointerBackend]] = JsonPointer  # pure-Python default


T_co = TypeVar("T_co", bound=JSONValue, covariant=True)


@final
class JSONPointer(str, Generic[T_co]):
    """
    A typed RFC 6901 JSON Pointer with Pydantic integration.

    ``JSONPointer[T]`` is a string-like value (subclasses ``str``) that additionally:

    - stores a parsed pointer backend (see ``PointerBackend``),
    - tracks a type parameter ``T`` used to validate resolved targets,
    - provides convenience methods for patch-like operations: ``get``, ``set``, ``delete``.

    Notes:
        - A backend is selected at validation time via Pydantic context under the key
          ``"jsonpatch:pointer_backend"``.
        - Default backend: ``jsonpointer.JsonPointer``; custom backend: provided by ``OperationRegistry``.
        - Invalid pointer strings raise ``InvalidJSONPointer``.
        - Backend traversal failures in ``get``/``set``/``delete`` are normalized into
          ``PatchApplicationError``.
        - Type mismatches between the resolved target and ``T`` raise ``PatchApplicationError``.
        - ``set`` and ``delete`` mutate the document object they are given (or containers reachable
          from it). The root pointer ``""`` is the exception: setting the root returns a new document
          value rather than mutating an existing container.
        - Whether these mutations affect the original caller-owned document is determined by the patch
          engine (see ``_apply_ops(..., inplace=...)``), which may deep-copy the input document.
        - ``JSONPointer`` values are intended to be created by Pydantic validation. Direct instantiation
          is not permitted (except when running as ``__main__`` for debugging).
    """

    # Choice: JSONPointer is str subclass, as opposed to Annotated[str, StringConstraints(...)].
    # Why: Cache adapters and pointers where possible, and provide simple primitives like get/set
    #      out-of-the-box, owned by the field, so path.get(doc) just works. Most users don't need
    #      more advanced functionality, so don't require them to reason about the PointerBackend API.
    # Considered: From a mutation point of view, consider reversing ownership to something like doc.get(path).
    #             Downside would be maintaining a JSONDocument wrapper around JSONValues, and taking power
    #             away from the PointerBackend implementation, which should really own the mutation logic.
    # Also considered: Performance drawback (https://docs.pydantic.dev/latest/concepts/performance/?utm_source=chatgpt.com#avoid-extra-information-via-subclasses-of-primitives).
    #                  I may replace str inheritance with a str property that derives from str(self._ptr).
    #                  But I like the idea that users think of JSONPointer[T] as the path string with extra abilities.

    __slots__ = ("_ptr", "_type")

    _ptr: PointerBackend
    _type: TypeForm[T_co]

    @property
    def ptr(self) -> Any:
        """
        The underlying parsed pointer backend instance.

        This is exposed for advanced users who provide a custom PointerBackend with additional APIs.
        The patch engine relies only on the ``PointerBackend`` protocol.
        """
        # TODO: Somehow 'Any' to the actual JSON Pointer class they pass in.
        # Choice: expose ptr as the user's custom PointerBackend for stronger type inferencing.
        # Why: This library only needs the PointerBackend Protocol, if some users want a custom
        #      PointerBackend, then expose that richer API to those users at type-checker time.
        return self._ptr

    @property
    def parts(self) -> Sequence[str]:
        """A sequence of RFC6901-unescaped pointer components."""
        return self._ptr.parts

    @property
    def type_param(self) -> TypeForm[T_co]:
        """The expected type parameter ``T`` used to validate resolved targets."""
        return self._type

    @property
    def _adapter(self) -> TypeAdapter[T_co]:
        return _type_adapter_for(self._type)

    @property
    def _parent_ptr(self) -> PointerBackend:
        # NOTE: Cache this outside too?
        return self._ptr.from_parts(self.parts[:-1])

    def __new__(
        cls,
        path: str,
        expected_type: TypeForm[T_co],
        *args: object,
        pointer_cls: type[PointerBackend] = _DEFAULT_POINTER_CLS,
        **kwargs: object,
    ) -> Self:
        if __name__ != "__main__":
            # Choice: Prevent non-Pydantic instantiation. Enable direct instantion for debugging only.
            # Why: JSONPointer[T] is only meant for Pydantic, why allow otherwise?
            raise TypeError(
                "JSONPointer values are created by Pydantic validation only."
            )
        if not isinstance(path, str):  # prevent casting
            raise InvalidJSONPointer(f"invalid JSON Pointer: {path!r} is not a string")
        obj = str.__new__(cls, path)
        obj._ptr = _json_pointer_for(path, pointer_cls=pointer_cls)
        obj._type = expected_type
        _type_adapter_for(expected_type)  # try to cache the adapter
        return obj

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> cs.CoreSchema:
        # Pydantic passes the parameterized type (JSONPointer[JSONString, JSONBoolean]) as source_type
        args = get_args(source_type)
        if not args:
            raise InvalidJSONPointer(
                "JSONPointer must be parameterized, e.g. JSONPointer[JSONNumber, JSONNumber]"
            )
        elif 1 < len(args):
            raise InvalidJSONPointer(
                f"JSONPointer may only have 1 parameter, got {len(args)}: {args}"
            )
        else:
            expected_type: TypeForm[T_co] = cast(TypeForm[T_co], args[0])

        def validator(path: str | Self, info: ValidationInfo) -> Self:
            if not isinstance(
                path, str
            ):  # defensive (prevent casting), but str_schema(strict=True) should prevent
                raise InvalidJSONPointer(
                    f"invalid JSON Pointer: {path!r} is not a string"
                )

            # Fetch PointerBackend from the registry's validation context, if present
            ctx = info.context or {}
            pointer_cls = cast(
                type[PointerBackend],
                ctx.get(_POINTER_BACKEND_CTX_KEY, _DEFAULT_POINTER_CLS),
            )

            # If path is already a JSONPointer with the same PointerBackend, don't rebuild.
            if isinstance(path, JSONPointer) and isinstance(path._ptr, pointer_cls):
                return path

            # Build
            obj = str.__new__(cls, path)
            obj._ptr = _json_pointer_for(path, pointer_cls=pointer_cls)
            obj._type = expected_type
            _type_adapter_for(expected_type)  # try to cache it
            return obj

        return cs.with_info_after_validator_function(
            function=validator,
            # Choice: Do NOT use pattern=re.compile(r"^(?:\/(?:[^~/]|~[01])*)*$") inside str_schema.
            # Why: Let the PointerBackend perform validation, which may be customized (e.g. handling of escapes).
            schema=cs.str_schema(strict=True),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> dict[str, object]:
        json_schema = handler(schema)
        json_schema.update(
            {
                "type": "string",
                "format": "json-pointer",
                "description": "JSON Pointer (RFC 6901) string",
            }
        )
        return json_schema

    def _validate_target(self, target: object) -> T_co:
        """
        Validate a target against this pointer's type.

        Args:
            target: Value to validate against ``T``.

        Returns:
            The validated value.

        Raises:
            PatchApplicationError: If validation fails.
        """
        try:
            return self._adapter.validate_python(target, strict=True)
        except Exception as e:
            raise PatchApplicationError(
                f"invalid target type {type(target).__name__} for pointer {str(self)!r}"
            ) from e

    def is_valid_target(self, target: object) -> bool:
        """Validate whether a target conforms to this pointer's type."""
        try:
            self._adapter.validate_python(target, strict=True)
            return True
        except Exception:
            return False

    def is_root(self) -> bool:
        """Check whether this JSONPointer's target is the root."""
        return self == ""

    def is_parent_of(self, other: JSONPointer[Any]) -> bool:
        """
        Check whether this JSONPointer's path is a parent of the `other` JSONPointer's path.

        Root is treated as a parent of all paths.
        """
        # Strict parentage only
        if self == other:
            return False

        return other.parts[: len(self.parts)] == self.parts

    def get(self, doc: JSONValue) -> T_co:
        """
        Resolve this pointer against ``doc`` and return the target value.

        The returned value is validated against the pointer's type parameter ``T``.

        Args:
            doc: Target JSON document.

        Returns:
            The resolved value, validated against ``T``.

        Raises:
            PatchApplicationError: If the pointer cannot be resolved (missing object member,
                out-of-range array index, or backend traversal failure) or if the resolved value
                does not conform to ``T``.
        """
        # Choice: always defer to the PointerBackend implementation for pointer resolution.
        # Why: Don't reinvent the wheel (and maintain it). Plus, give more power to custom PointerBackends.
        try:
            target = self._ptr.resolve(doc)
        except Exception as e:
            raise PatchApplicationError(f"path {str(self)!r} not found: {e}") from e
        return self._validate_target(target)

    def is_gettable(self, doc: JSONValue) -> bool:
        """Return True if ``get`` would succeed for this document, else False."""
        try:
            self.get(doc)
        except Exception:
            return False
        else:
            return True

    def set(
        self, doc: JSONValue, value: JSONValue, *, validate_value: bool = True
    ) -> JSONValue:
        """
        Set the value at this pointer path in ``doc`` and return the updated document.

        - If this pointer is the root (``""``), returns ``value`` as the new document.
        - Otherwise, resolves the parent container and writes the value into that container,
          mutating the *provided* document object in-place.
        - For arrays, the value is inserted at the index (RFC 6902 add semantics). ``"-"`` appends.

        Important: whether this affects your *original* document depends on how you obtained ``doc``.
        In patch application, the patch engine may first deep-copy the input document before calling
        operations/JSONPointer methods.

        By default, ``value`` is validated against the pointer's type parameter ``T``.

        Args:
            doc: Target JSON document.
            value: Value to set at this path.
            validate_value: If True, validate ``value`` against ``T`` before setting.

        Returns:
            The updated document (or the new root value for ``""``).

        Raises:
            PatchApplicationError: If the path cannot be resolved, the parent is not a container,
                or the final token is not a valid container key.
        """
        # Type errors first
        target: JSONValue
        if validate_value:
            target = self._validate_target(target=value)
        else:
            target = value

        if self.is_root():
            return target
        try:
            container = self._parent_ptr.resolve(doc)
        except Exception as e:
            raise PatchApplicationError(f"path {str(self)!r} not found: {e}") from e
        if not _is_container(container):
            raise PatchApplicationError(
                f"cannot set value at {str(self)!r} because {self._parent_ptr} resolves to a JSON primitive"
            )
        key = _parse_JSONContainer_key(container, self.parts[-1])
        if isinstance(container, dict):
            container[key] = target
        elif key == "-":
            container.append(target)
        else:
            assert isinstance(key, int), "internal error: set"
            container.insert(key, target)
        return doc

    def is_settable(
        self,
        doc: JSONValue,
        value: object = _Nothing,
        *,
        validate_value: bool = True,
    ) -> bool:
        """
        Return True if ``set`` would succeed for this document (and optional value), else False.

        If ``value`` is provided and ``validate_value`` is True, it must conform to the
        pointer's type parameter ``T``.
        """
        try:
            if value is not _Nothing and validate_value:
                if not self.is_valid_target(value):
                    return False
            if self.is_root():
                return True
            container = self._parent_ptr.resolve(doc)
            if not _is_container(container):
                return False
            _parse_JSONContainer_key(container, self.parts[-1])
        except Exception:
            return False
        else:
            return True

    def delete(self, doc: JSONValue) -> JSONValue:
        """
        Delete the target value at this pointer path and return the updated document.

        This mutates the *provided* document object in-place. Whether this affects your *original*
        document depends on the patch engine: in typical patch application, the engine may deep-copy
        the input document first (``inplace=False``) before applying operations.

        Args:
            doc: Target JSON document.

        Returns:
            The mutated document.

        Raises:
            PatchApplicationError: If the pointer is the root or the target does not exist.

        Notes:
            - Deleting the root (``""``) is not allowed.
            - Deleting a missing target raises ``PatchApplicationError``.
        """
        if self.is_root():
            # Choice: Deletion returns None at the root.
            # Why: Keeps the system composable, predictable, and closed over JSONValue.
            #      It affects few users, who themselves can circumvent with custom ops.
            return None
        if not self.is_gettable(doc):
            raise PatchApplicationError("cannot delete a missing target")
        try:
            container = cast(JSONContainer[JSONValue], self._parent_ptr.resolve(doc))
            assert isinstance(container, (dict, list)), "internal error: delete"
        except Exception as e:
            raise PatchApplicationError(f"path {str(self)!r} not found: {e}") from e
        key = _parse_JSONContainer_key(container, self.parts[-1])
        if key == "-" and not isinstance(container, dict):
            raise PatchApplicationError(
                f"cannot delete value at {str(self)!r} with key '-'"
            )
        del container[key]  # type: ignore[arg-type]
        return doc

    @override
    def __repr__(self) -> str:
        if isinstance(self._type, type):
            type_repr = self._type.__name__
        else:
            type_repr = repr(self._type)
        return f"{self.__class__.__name__}[{type_repr}]({str(self)!r})"
