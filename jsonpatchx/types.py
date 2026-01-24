from __future__ import annotations

import re
from abc import abstractmethod
from collections.abc import Iterable, Sequence
from functools import lru_cache, partial
from inspect import isclass
from typing import (
    Annotated,
    Any,
    Callable,
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

from jsonpatchx.exceptions import (
    InvalidJSONPointer,
    PatchConflictError,
)

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

type _JSONArrayKey = Annotated[int, Field(ge=0)] | Literal["-"]
type _JSONObjectKey = str
type _JSONKey = _JSONArrayKey | _JSONObjectKey

_ARRAY_INDEX_PATTERN: re.Pattern[str] = re.compile(r"^(0|[1-9][0-9]*)$")


def _parse_JSONArray_key(array: JSONArray[JSONValue], key: str) -> _JSONArrayKey:
    """# NOTE document that it follows add semantics (key==len(array) allowed) and remove must tighten restrictions
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
        raise PatchConflictError(f"invalid array index: {key!r}")
    idx = int(key)
    if idx > len(array):
        raise PatchConflictError(f"index out of range: {key!r}")
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
        - ``PointerBackend("")`` must be valid return the root pointer.`
        - Round-trip invariants should hold:
          ``PointerBackend(x)`` equals ``PointerBackend(str(PointerBackend(x)))`` and
          ``PointerBackend(x)`` equals ``PointerBackend.from_parts(PointerBackend(x).parts)``.
        - The library may cache backend instances; implementations should be immutable or otherwise
          safe to reuse across calls.
        - Backends may raise whatever exceptions are natural for them. Higher-level APIs normalize
          backend failures into library patch errors for a consistent user experience.
    """

    # NOTE: with init defined, this protocol is counter-intuitively instantiable without the @abstractmethod later on __hash__
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

    @override
    @abstractmethod  # NOTE: if mutable, unhashable backends are compelling, can loosen this requirement
    def __hash__(self) -> int: ...


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


_POINTER_BACKEND_CTX_KEY: Final = "jsonpatch:pointer_backend"
_DEFAULT_POINTER_CLS: Final = JsonPointer  # pure-Python default


_Nothing = object()
# NOTE: maybe add pydantic_core.MISSING to JSONPointer.get() on failure


T_co = TypeVar("T_co", bound=JSONValue, covariant=True)
P_co = TypeVar("P_co", bound=PointerBackend, covariant=True, default=PointerBackend)


@final
class JSONPointer(str, Generic[T_co, P_co]):
    """
    A typed RFC 6901 JSON Pointer with Pydantic integration.

    ``JSONPointer[T]`` (or ``JSONPointer[T, Backend]``) is a string-like value (subclasses ``str``)
    that additionally:

    - stores a parsed pointer backend (see ``PointerBackend``),
    - tracks a covariant type parameter ``T`` used to validate resolved targets,
    - provides convenience methods used by patch operations: ``get``, ``add``, ``remove``.

    ## Important design semantics (intentional)

    **Typed pointers are enforced at runtime.**
    The type parameter ``T`` is not “just typing”; it is enforced whenever a value is read
    through the pointer.

    - ``get(doc)`` always validates the resolved value against ``T``.
    - ``add(doc, value)`` optionally validates the written value against ``T`` (default: True).
    - ``remove(doc)`` is intentionally *type-gated*: it first “reads” the target through the pointer,
      so removal can fail if the current value is not of type ``T``.

    This makes patch semantics explicit:
    - ``JSONPointer[JSONValue]`` is permissive (“remove anything JSON”).
    - ``JSONPointer[JSONBoolean]`` is restrictive (“remove only if it is currently a boolean”).
    - If you want to remove regardless of the current type, use a wider pointer type (e.g. ``JSONValue``)
      or define a dedicated permissive remove operation.

    **Pointer covariance is intentional.**
    ``JSONPointer`` is covariant in ``T``. In practice this means you can often reuse a pointer instance
    (including across composed operations) and preserve stricter guarantees.
    Example: if a custom op carries a ``JSONPointer[JSONBoolean]``, composing that op internally
    using ``AddOp`` should keep the boolean-specific enforcement at runtime.

    ## Backend semantics (advanced)

    - A backend is selected at validation time via Pydantic context under the key
      ``"jsonpatch:pointer_backend"``.
    - Default backend: ``jsonpointer.JsonPointer``; custom backend: provided by ``OperationRegistry`` or
      bound directly via ``JSONPointer[T, Backend]``.
    - Invalid pointer strings raise ``InvalidJSONPointer``.
    - Backend traversal failures in ``get``/``add``/``remove`` are normalized into
      ``PatchConflictError``.

    Mutation semantics:
    - ``add`` and ``remove`` may mutate the document object they are given (or containers reachable
      from it). The root pointer ``""`` is the exception: setting the root returns a new document
      value rather than mutating an existing container. Removing the root sets it to JSONNull (None)
      so that all standard operations are closed over JSONValue. If you wan't for forbid root removal,
      it's easy to make a custom op!
    - Whether these mutations affect the original caller-owned document is determined by the patch
      engine (see ``_apply_ops(..., inplace=...)``), which may deep-copy the input document.

    ``JSONPointer`` values are intended to be created by Pydantic validation. Direct instantiation
    is not permitted (except when running as ``__main__`` for debugging).
    """

    # Choice: JSONPointer is str subclass, as opposed to Annotated[str, StringConstraints(...)].
    # Why: Cache adapters and pointers where possible, and provide simple primitives like get/add
    #      out-of-the-box, owned by the field, so path.get(doc) just works. Most users don't need
    #      more advanced functionality, so don't require them to reason about the PointerBackend API.
    # Considered: From a mutation point of view, consider reversing ownership to something like doc.get(path).
    #             Downside would be maintaining a JSONDocument wrapper around JSONValues, and taking power
    #             away from the PointerBackend implementation, which should really own the mutation logic.
    # Also considered: Performance drawback (https://docs.pydantic.dev/latest/concepts/performance/?utm_source=chatgpt.com#avoid-extra-information-via-subclasses-of-primitives).
    #                  I may replace str inheritance with a str property that derives from str(self._ptr).
    #                  But I like the idea that users think of JSONPointer[T] as the path string with extra abilities.

    __slots__ = ("_ptr", "_type")

    _ptr: P_co
    _type: TypeForm[T_co]

    @property
    def ptr(self) -> P_co:
        """
        The underlying pointer backend instance.

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
    def _parent_ptr(self) -> P_co:
        # NOTE: Cache this outside too?
        return self._ptr.from_parts(self.parts[:-1])

    def is_root(self) -> bool:
        """Check whether this JSONPointer's target is the root."""
        return self == ""

    def _hidden_init(
        cls,
        path: str,
        type_param: TypeForm[T_co],
        *args: object,
        pointer_cls: type[P_co] = cast(type[P_co], PointerBackend),
        **kwargs: object,
    ) -> Self:
        """Private way to instantiate JSONPointer directly."""
        if pointer_cls is PointerBackend:
            pointer_cls = _DEFAULT_POINTER_CLS
        _, __ = cls._parse_pointer_type_args(type_param, pointer_cls)

        return cls._validator(
            path, registry_info=None, type_param=type_param, bound_backend=pointer_cls
        )

    @classmethod
    def _validator(
        cls,
        path: str,
        registry_info: ValidationInfo | None,
        *,
        type_param: TypeForm[T_co],
        bound_backend: type[P_co] | None,
    ) -> Self:
        """
        Validator function for JSONPointer.

        Assumes ``registry_info``, ``type_param``, and ``bound_backend`` are all valid, if povided.
        """
        # Fetch PointerBackend from the registry's validation context, if present
        ctx = registry_info.context or {} if registry_info is not None else {}
        registry_backend = cast(
            type[PointerBackend] | None, ctx.get(_POINTER_BACKEND_CTX_KEY)
        )

        # Enforce registry_backend ⊆ bound_backend ⊂ PointerBackend and get the strictest one
        strictest_protocol = cls._resolve_strictest_backend(
            registry_backend, bound_backend
        )

        # Build it
        obj: Self = str.__new__(cls, path)

        # Try to reuse the type parameters (type checkers already enforce covariance)
        if isinstance(path, JSONPointer):
            if (
                isclass(path._type)
                and isclass(type_param)
                and not issubclass(path._type, type_param)
            ):
                # Ideally, compare TypeAdapters to cover all TypeForm covariance, but Pydantic doesn't expose subtype relation.
                raise InvalidJSONPointer(
                    f"Expected {type_param}, got: {path._type}. JSONPointer[T] is covariant in type T."
                )
            obj._type = path._type
        else:
            obj._type = type_param

        # If path is a JSONPointer with a compatible backend, reuse the backend
        if isinstance(path, JSONPointer) and isinstance(path._ptr, strictest_protocol):
            obj._ptr = cast(P_co, path._ptr)
        else:
            pointer_cls = (
                strictest_protocol
                if strictest_protocol is not PointerBackend
                else _DEFAULT_POINTER_CLS
            )
            obj._ptr = _cached_json_pointer(path, pointer_cls=pointer_cls)

        return obj

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> cs.CoreSchema:
        type_param, bound_backend = cls._parse_pointer_type_args(*get_args(source_type))
        validator_function = partial(
            cls._validator, type_param=type_param, bound_backend=bound_backend
        )
        return cs.with_info_after_validator_function(
            function=validator_function,
            schema=cs.union_schema(
                [cs.is_instance_schema(JSONPointer), cs.str_schema(strict=True)]
            ),
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

    @classmethod
    def _parse_pointer_type_args(
        cls, *args: Any
    ) -> tuple[TypeForm[T_co], type[P_co] | None]:
        """Validate the JSONPointer's parameter tuple, e.g. ``(JSONValue, DotPointer)`` for ``JSONPointer[JSONValue, DotPointer]``."""
        if not (1 <= len(args) <= 2):
            raise InvalidJSONPointer(
                f"JSONPointer requires 1 or 2 parameters, e.g. JSONPointer[JSONValue], got {len(args)!r}: {args}"
            )
        type_param = cast(object, args[0])
        bound_backend: type | None = cast(type, args[1]) if len(args) == 2 else None

        # Protocol itself doesn't count
        if bound_backend is PointerBackend:
            bound_backend = None

        if not cls._is_valid_typeform(type_param):
            raise InvalidJSONPointer(
                f"JSONPointer type parameter {type_param!r} must be a valid TypeForm"
            )
        if bound_backend is not None and not cls._implements_PointerBackend_protocol(
            bound_backend
        ):
            raise InvalidJSONPointer(
                f"JSONPointer backend parameter {bound_backend!r} instances must implement the PointerBackend Protocol"
            )
        return type_param, bound_backend

    @classmethod
    def _is_valid_typeform(cls, expected: object) -> TypeGuard[TypeForm[T_co]]:
        """Validate the TypeForm parameter."""
        try:
            _type_adapter_for(expected)  # type: ignore[arg-type]
        except Exception:
            return False
        return True

    @staticmethod
    def _implements_PointerBackend_protocol(
        pointer_cls: type,
    ) -> TypeGuard[type[P_co]]:
        """Verifies a ``PointerBackend`` implementation using the empty string as a probe."""
        try:
            probe = _cached_json_pointer(path="", pointer_cls=pointer_cls)
        except TypeError as e:
            raise InvalidJSONPointer(
                f"the pointer class {pointer_cls!r} must be hashable"
            ) from e
        except Exception as e:
            raise InvalidJSONPointer(
                f"invalid pointer class: {pointer_cls!r}, fails to convert  to pointer"
            ) from e

        return isinstance(probe, PointerBackend)

    @staticmethod
    def _resolve_strictest_backend(
        registry_backend: type[PointerBackend] | None,
        bound_backend: type[PointerBackend] | None,
    ) -> type[PointerBackend]:
        """Determine the strictest PointerBackend class, given optional ``registry_backend`` and ``bound_backend``."""
        if registry_backend is not None and bound_backend is not None:
            if not issubclass(registry_backend, bound_backend):
                raise InvalidJSONPointer(
                    "JSONPointer backend mismatch: "
                    f"registry requires {registry_backend.__name__} but field uses "
                    f"{bound_backend.__name__}"
                )
            return registry_backend
        if registry_backend is not None:
            return registry_backend
        if bound_backend is not None:
            return bound_backend
        return PointerBackend

    def _validate_target(self, target: object) -> T_co:
        """Strictly validate the ``target`` with this JSONPointer's TypeAdapter."""
        try:
            return self._adapter.validate_python(target, strict=True)
        except Exception as e:
            raise PatchConflictError(
                f"expected target type {self.type_param} for pointer {str(self)!r}, got: {type(target)}"
            ) from e

    # Parse-time helpers

    def is_parent_of(self, other: str) -> bool:
        """
        Check whether this pointer is a parent of `other`.

        `other` may be a JSONPointer or a pointer string; strings are parsed using this pointer's syntax.

        Root is treated as a parent of all paths.

        Raises InvalidJSONPointer if comparison is called with an `other` pointer with different or invalid syntax.
        """
        if isinstance(other, JSONPointer) and not isinstance(
            other._ptr, type(self._ptr)
        ):
            raise InvalidJSONPointer(
                f"other pointer {other._ptr!r} has incompatible syntax with {self!r}"
            )
        other_ptr: P_co = _cached_json_pointer(other, pointer_cls=type(self._ptr))

        # Strict parentage only
        if self == str(other_ptr):
            return False

        return other_ptr.parts[: len(self.parts)] == self.parts

    def is_child_of(self, other: str) -> bool:
        """
        Check whether this pointer is a child of `other`.

        `other` may be a JSONPointer or a pointer string; strings are parsed using this pointer's syntax.

        Root is treated as a parent of all paths.

        Raises InvalidJSONPointer if comparison is called with an `other` pointer with different or invalid syntax.
        """
        if isinstance(other, JSONPointer) and not isinstance(
            other._ptr, type(self._ptr)
        ):
            raise InvalidJSONPointer(
                f"other pointer {other._ptr!r} has incompatible syntax with {self!r}"
            )
        other_ptr: P_co = _cached_json_pointer(other, pointer_cls=type(self._ptr))

        # Strict parentage only
        if self == str(other_ptr):
            return False

        return self.parts[: len(other_ptr.parts)] == other_ptr.parts

    # Runtime helpers

    def is_valid_target(self, target: object) -> bool:
        """Validate whether a target conforms to this pointer's type."""
        try:
            self._adapter.validate_python(target, strict=True)
            return True
        except Exception:
            return False

    def get(self, doc: JSONValue) -> T_co:
        """
        Resolve this pointer against ``doc`` and return the target value (type-gated).

        Args:
            doc: Target JSON document.

        Returns:
            The resolved value, validated against ``T``.

        Raises:
            PatchConflictError: If the target does not exist, or it is not type ``T``.
        """
        # Choice: always defer to the PointerBackend implementation for pointer resolution.
        # Why: Don't reinvent the wheel (and maintain it). Plus, give more power to custom PointerBackends.
        try:
            target = self._ptr.resolve(doc)
        except Exception as e:
            raise PatchConflictError(f"path {str(self)!r} not found: {e}") from e
        return self._validate_target(target)

    def is_gettable(self, doc: JSONValue) -> bool:
        """Return True if ``get`` would succeed for this document, else False."""
        try:
            self.get(doc)
        except Exception:
            return False
        else:
            return True

    def add(self, doc: JSONValue, value: JSONValue) -> JSONValue:
        """
        RFC 6902 add (type-gated).

        Args:
            doc: Target JSON document.
            value: Value to add at this path, validated against ``T``.

        Returns:
            The updated document.

        Raises:
            PatchConflictError: If the target does not exist, or it is not type ``T``.
        """
        # Type errors first
        target = self._validate_target(target=value)

        if self.is_root():
            return target
        try:
            container = self._parent_ptr.resolve(doc)
        except Exception as e:
            raise PatchConflictError(f"path {str(self)!r} not found: {e}") from e
        if not _is_container(container):
            raise PatchConflictError(
                f"path {str(self._parent_ptr)!r} resolves to a JSON primitive"
            )
        key = _parse_JSONContainer_key(container, self.parts[-1])
        if isinstance(container, dict):
            container[key] = target
        elif key == "-":
            container.append(target)
        else:
            assert isinstance(key, int), "internal error: add"
            container.insert(key, target)
        return doc

    def is_addable(
        self,
        doc: JSONValue,
        value: object = _Nothing,
    ) -> bool:
        """
        Return True if ``add`` would succeed for this document (and optional value), else False.

        If ``value`` is provided, it must conform to the pointer's type parameter ``T``.
        """
        try:
            if value is not _Nothing and not self.is_valid_target(value):
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

    def remove(self, doc: JSONValue) -> JSONValue:
        """
        RFC 6902 remove (type-gated). Removal of the root sets it to null.

        Args:
            doc: Target JSON document.

        Returns:
            The updated document.

        Raises:
            PatchConflictError: If the target does not exist, or it is not type ``T``.
        """
        if self.is_root():
            # Choice: Removal of root sets root to null.
            # Why: Keeps all operations closed over JSONValue. Remove is also more composable this way.
            #      It affects few users, who themselves can circumvent with custom ops.
            return None
        try:
            container = self._parent_ptr.resolve(doc)
        except Exception as e:
            raise PatchConflictError(f"path {str(self)!r} not found: {e}") from e
        if not _is_container(container):
            raise PatchConflictError(
                f"path {str(self._parent_ptr)!r} resolves to a JSON primitive"
            )
        key = _parse_JSONContainer_key(container, self.parts[-1])
        if isinstance(container, list):
            if key == "-":
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} with key '-'"
                )
            elif key == len(container):
                raise PatchConflictError(f"index out of range: {key!r}")
        elif isinstance(container, dict):
            if key not in container:
                raise PatchConflictError(
                    f"target {key!r} does not exist in object at path {str(self._parent_ptr)!r}"
                )
        self._validate_target(container[key])
        del container[key]
        return doc

    @override
    def __repr__(self) -> str:
        if isinstance(self._type, type):
            type_repr = self._type.__name__
        else:
            type_repr = repr(self._type)
        return f"{self.__class__.__name__}[{type_repr}]({str(self)!r})"


assert JSONPointer._implements_PointerBackend_protocol(_DEFAULT_POINTER_CLS), (
    "upstream regression: jsonpointer.JsonPointer no longer implements PointerBackend protocol"
)
