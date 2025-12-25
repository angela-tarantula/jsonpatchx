from __future__ import annotations

import json
import math
from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence
from functools import lru_cache
from typing import (
    Annotated,
    Any,
    Literal,
    Protocol,
    Self,
    cast,
    final,
    get_args,
    overload,
    override,
    runtime_checkable,
)

from jsonpointer import (  # type: ignore[import-untyped]
    JsonPointer,
    JsonPointerException,
)
from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    TypeAdapter,
)
from pydantic_core import core_schema as cs
from typing_extensions import TypeForm

from jsonpatch.exceptions import (
    InvalidJSONPointer,
    InvalidOperationSchema,
    PatchApplicationError,
)


class JSONValueValidator:
    """Pydantic-aware wrapper for any JSON-serializable value."""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> cs.CoreSchema:
        return cs.no_info_after_validator_function(
            cls._validate,
            cs.any_schema(),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: cs.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        json_schema = handler(core_schema)
        json_schema.update({"description": "JSON Value."})
        return json_schema

    @classmethod
    def _validate(cls, v: object) -> JSONValue:
        try:
            json.dumps(v, allow_nan=False)  # TODO: use orjson when threadsafe
        except (TypeError, ValueError) as e:
            raise InvalidOperationSchema(
                f"Value is not JSON-serializable: {v!r}"
            ) from e
        return cast(JSONValue, v)


class JSONNumberValidator:
    """Pydantic-aware wrapper for JSON numbers."""

    __slots__ = ()

    @classmethod
    def __get_pydantic_core_schema__(
        cls,
        source_type: type[Any],
        handler: GetCoreSchemaHandler,
    ) -> cs.CoreSchema:
        return cs.no_info_after_validator_function(
            cls._validate,
            cs.union_schema(
                [
                    cs.float_schema(strict=True),
                    cs.int_schema(strict=True),
                ]
            ),
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        schema: cs.CoreSchema,
        handler: GetJsonSchemaHandler,
    ) -> dict[str, object]:
        json_schema = handler(schema)
        json_schema.update({"description": "JSON Number"})
        return json_schema

    @classmethod
    def _validate(cls, v: int | float) -> JSONNumber:
        # bool is a subclass of int, so exclude it explicitly
        if type(v) is bool or not isinstance(v, (int, float)):
            raise InvalidOperationSchema(
                f"expected JSON number (int|float, finite), not {v.__class__.__name__}: {v!r}"
            )
        if isinstance(v, float) and not math.isfinite(v):
            raise InvalidOperationSchema(f"expected finite JSON number, got {v!r}")
        return v


# Core JSON type aliases

type JSONBoolean = bool
type JSONNumber = Annotated[int | float, JSONNumberValidator]
type JSONString = str
type JSONNull = None
type JSONPrimitive = JSONBoolean | JSONNumber | JSONString | JSONNull

type JSONArray[T_co] = Sequence[T_co]
type JSONObject[T_co] = Mapping[str, T_co]
type JSONContainer[T_co] = JSONArray[T_co] | JSONObject[T_co]

type MutableJSONArray[T_co] = MutableSequence[T_co]
type MutableJSONObject[T_co] = MutableMapping[str, T_co]
type MutableJSONContainer[T_co] = MutableJSONArray[T_co] | MutableJSONObject[T_co]

type JSONValue = Annotated[
    JSONPrimitive | JSONContainer[JSONValue],
    JSONValueValidator,
]

MISSING = object()


@runtime_checkable
class PointerBackend(Protocol):
    @property
    def parts(self) -> tuple[str, ...]:
        """RFC6901-unescaped tokens. Root => ()."""
        ...

    def resolve(self, doc: Any, *, default: Any) -> Any:
        """Resolve pointer against doc. Return default or raise."""

    @override
    def __str__(self) -> str:
        """Get the string representation of the pointer (escaped)."""
        ...


@lru_cache(maxsize=128)
def _cached_type_adapter[T](expected: TypeForm[T]) -> TypeAdapter[T]:
    return TypeAdapter(expected)


@lru_cache(maxsize=128)
def _cached_json_pointer(ptr: str) -> JsonPointer:
    return JsonPointer(ptr)


def _type_adapter_for[T](expected: TypeForm[T]) -> TypeAdapter[T]:
    """Get a cached type adapter if possible, otherwise create a new one."""
    try:
        try:
            return _cached_type_adapter(expected)  # type: ignore[arg-type]
        except TypeError:
            return TypeAdapter(expected)
    except Exception as e:
        raise InvalidJSONPointer(
            f"invalid type parameter for JSON Pointer: {expected!r}"
        ) from e


def _json_pointer_for(v: str) -> JsonPointer:
    """Get a cached JSON pointer."""
    try:
        return _cached_json_pointer(v)
    except (JsonPointerException, TypeError) as e:
        # defensive to except TypeError, it's for cache errors (if v is not str at runtime)
        raise InvalidJSONPointer(f"invalid JSON Pointer: {v!r}") from e


@final
class JSONPointer[T: JSONValue](str):
    """
    RFC 6901 JSON Pointer. Runtime value produced by Pydantic for a field annotated as JSONPointer[IN, OUT].

    - Subclasses str so user code can treat it like the pointer string.
    - Stores parsed JsonPointer for structural ops
    - Stores TypeAdapter[T] for apply-time validation
    """

    __slots__ = ("_ptr", "_adapter", "_type_repr")

    _ptr: JsonPointer
    _adapter: TypeAdapter[T]

    @property
    def _type(self) -> TypeForm[T]:
        # Shamelessly relies on a private attribute, TypeAdapter._type, to get the JSONPointer type.
        # In my opinion, TypeAdapter._type should be a public type, and I'll die on this hill.
        # If I had JSONPointer._adapter and JSONPointer._type, there'd be two sources of truth.
        # JSONPointer._type would be a derived field, and I'm too purist to implement it.
        return cast(TypeForm[T], self._adapter._type)

    def __new__(cls, *_: object, **__: object) -> Self:
        raise TypeError("JSONPointer values are created by Pydantic validation only.")

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
            expected_type: TypeForm[T] = cast(TypeForm[T], args[0])

        def initializer(v: str) -> Self:
            if type(v) is not str:  # defensive
                raise InvalidJSONPointer(f"invalid JSON Pointer: {v!r} is not a string")
            obj = str.__new__(cls, v)
            obj._ptr = _json_pointer_for(v)
            obj._adapter = _type_adapter_for(expected_type)
            return obj

        return cs.no_info_after_validator_function(
            function=initializer,
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

    def validate_target(self, target: object) -> T:
        """
        Validate a target against this pointer's type.

        Raises PatchApplicationError on failure.
        """
        try:
            return self._adapter.validate_python(target, strict=True)
        except Exception as e:
            raise PatchApplicationError(
                f"invalid target type {type(target).__name__} for pointer {str(self)!r}"
            ) from e

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

        # Due to a bug in the upstream `jsonpointer` library, where jp1.contains(root_pointer)`
        # is always False, we special-case root:
        if self.is_root():
            return True

        return cast(bool, self._ptr.contains(other._ptr))

    @overload
    def resolve_last(
        self,
        doc: JSONValue,
        *,
        exists: Literal[True],
        mutable: Literal[True],
        container: Literal["object", "array"] | None = None,
    ) -> tuple[MutableJSONObject[T], str] | tuple[MutableJSONArray[T], int]: ...

    @overload
    def resolve_last(
        self,
        doc: JSONValue,
        *,
        exists: Literal[False] | None = None,
        mutable: Literal[True],
        container: Literal["object", "array"] | None = None,
    ) -> (
        tuple[MutableJSONObject[T], str]
        | tuple[MutableJSONArray[T], int | Literal["-"]]
    ): ...

    @overload
    def resolve_last(
        self,
        doc: JSONValue,
        *,
        exists: Literal[True],
        mutable: bool | None = None,
        container: Literal["object", "array"] | None = None,
    ) -> tuple[JSONObject[T], str] | tuple[JSONArray[T], int]: ...

    @overload
    def resolve_last(
        self,
        doc: JSONValue,
        *,
        exists: bool | None = None,
        mutable: bool | None = None,
        container: Literal["object", "array"] | None = None,
    ) -> tuple[JSONObject[T], str] | tuple[JSONArray[T], int | Literal["-"]]: ...

    def resolve_last(
        self,
        doc: JSONValue,
        *,
        exists: bool | None = None,
        mutable: bool | None = None,
        container: Literal["object", "array"] | None = None,
    ) -> tuple[JSONObject[T], str] | tuple[JSONArray[T], int | Literal["-"]]:
        """
        Resolve this JSON Pointer against a `doc` to its parent container and final token.

        Returns `(container, key)` such that `container[key]` is this JSONPointer's target.

        Constraints (optional):
        - exists: require target existence (True) or non-existence (False)
        - mutable: require container mutability (True) or immutability (False)
        - container: require parent container to be "object" or "array"

        The root of `doc` has no container and trying to `resolve_last` against it raises PatchApplicationError.
        """
        if self.is_root():
            raise PatchApplicationError(
                "tried to resolve a path to last, but got root, which has no container"
            )

        try:
            path_container, path_key = self._ptr.to_last(doc)
            assert isinstance(path_container, (Mapping, Sequence)) and not isinstance(
                path_container, (str, bytes, bytearray)
            ), "JsonPointer implementation changed"
        except JsonPointerException as e:
            raise PatchApplicationError(
                f"unable to resolve path {str(self)!r}: {e}"
            ) from e

        # container constraint
        if container == "object":
            if not isinstance(path_container, Mapping):
                raise PatchApplicationError(
                    f"expected object container at {str(self)!r}, got {type(path_container)!r}"
                )
        elif container == "array":
            if not isinstance(path_container, Sequence):
                raise PatchApplicationError(
                    f"expected array container at {str(self)!r}, got {type(path_container)!r}"
                )

        # mutability constraint
        if mutable is not None:
            is_mutable = isinstance(path_container, (MutableMapping, MutableSequence))
            if is_mutable is not mutable:
                if mutable:
                    raise PatchApplicationError(
                        f"expected mutable container at {str(self)!r}, got {type(path_container)!r}"
                    )
                raise PatchApplicationError(
                    f"expected immutable container at {str(self)!r}, got {type(path_container)!r}"
                )

        # existence constraint
        if exists is not None:
            try:
                target = path_container[path_key]
            except (KeyError, IndexError, TypeError) as e:
                # Missing key, index out of bounds, or invalid "-" access.
                if exists:
                    raise PatchApplicationError(
                        f"target at {str(self)!r} does not exist"
                    ) from e
            else:
                if exists:
                    self.validate_target(target=target)
                else:
                    raise PatchApplicationError(
                        f"target at {str(self)!r} already exists"
                    )

        return path_container, path_key

    def assert_target(
        self,
        doc: JSONValue,
        exists: bool | None = None,
        mutable: bool | None = None,
    ) -> None:
        """
        Assert invariants about this JSONPointer's target on a `doc`.

        The root of `doc` is always considered to exist and be writable.
        """
        if self.is_root():
            target = doc
            if mutable is False:
                raise PatchApplicationError(f"target at {str(self)!r} is mutable")
            if exists is False:
                raise PatchApplicationError(f"target at {str(self)!r} already exists")
            self.validate_target(target=target)
        else:
            self.resolve_last(doc, exists=exists, mutable=mutable)

    def get(self, doc: JSONValue) -> T:
        """
        Resolve the JSONPointer against the `doc` and return the target.
        """
        if self.is_root():
            return self.validate_target(target=doc)
        else:
            container, key = self.resolve_last(doc, exists=True)
            return container[key]  # type: ignore[index]

    def set(self, doc: JSONValue, value: T) -> JSONValue:
        new_target = self.validate_target(value)
        if self.is_root():
            return new_target

        container, key = self.resolve_last(doc, mutable=True)

        if isinstance(container, MutableMapping):
            container[key] = new_target  # type: ignore[index]
        elif isinstance(container, MutableSequence):
            if key == "-":
                key = len(container)
            if key > len(container):  # type: ignore[operator]
                raise PatchApplicationError(f"target at {str(self)!r} is out of range")
            assert key >= 0, "JsonPointer implementation changed"  # type: ignore[operator]
            container.insert(key, new_target)  # type: ignore[arg-type]

        return doc

    @override
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}[{self._type}]({str(self)!r})"
