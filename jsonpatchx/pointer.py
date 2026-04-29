from collections.abc import Sequence
from functools import partial
from inspect import isabstract
from typing import (
    Any,
    Generic,
    Self,
    assert_never,
    cast,
    final,
    get_args,
    overload,
    override,
)

from pydantic import (
    GetCoreSchemaHandler,
    GetJsonSchemaHandler,
    TypeAdapter,
    ValidationError,
)
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema as cs
from typing_extensions import TypeForm, TypeVar

from jsonpatchx.backend import (
    DEFAULT_POINTER_CLS,
    PointerBackend,
    TargetState,
    _is_root_ptr,
    _parent_ptr_of,
    _pointer_backend_instance,
    classify_state,
)
from jsonpatchx.exceptions import (
    InvalidJSONPointer,
    PatchConflictError,
)
from jsonpatchx.types import (
    JSONArray,
    JSONBound,
    JSONContainer,
    JSONObject,
    JSONValue,
    _cached_adapter,
    _is_array,
    _is_object,
    _validate_JSONValue,
    _validate_typeform,
)

_Nothing = object()


T_co = TypeVar("T_co", bound=JSONBound, covariant=True)
P_co = TypeVar(
    "P_co", bound=PointerBackend, covariant=True, default=DEFAULT_POINTER_CLS
)
T_parse = TypeVar("T_parse", bound=JSONBound, covariant=True)
P_parse = TypeVar("P_parse", bound=PointerBackend, default=DEFAULT_POINTER_CLS)


@final
class JSONPointer(str, Generic[T_co, P_co]):
    """
    A typed RFC 6901 JSON Pointer with Pydantic integration.

    `JSONPointer[T]` (or `JSONPointer[T, Backend]`) is a `str` subclass that
    parses a pointer string at validation time and enforces the type parameter `T`
    when a value is read or written through it. The string value is the pointer
    path itself, so `JSONPointer` is accepted wherever `str` is.

    Example:
        Use it as a field type in `OperationSchema` subclasses:

        ```python
        from typing import Literal
        from jsonpatchx import JSONPointer, OperationSchema, ReplaceOp, JsonPatch, JSONValue, JSONBoolean

        class ToggleBoolOp(OperationSchema):
            op: Literal[“toggle”] = “toggle”
            path: JSONPointer[JSONBoolean]

            def apply(self, doc: JSONValue) -> JSONValue:
                toggled = not self.path.get(doc)
                return ReplaceOp(path=self.path, value=toggled).apply(doc)

        ops = [ToggleBoolOp(path=”/flag”)]
        patch = JsonPatch(ops)
        doc = {“flag”: False}
        patched_doc = patch.apply(doc)
        assert patched_doc == {“flag”: True}
        ```

    Example:
        Plug in a custom pointer backend for non-RFC 6901 syntax:

        ```python
        from jsonpatchx import JSONPointer, JSONBoolean, PointerBackend

        class DotPointer(PointerBackend):
            ...  # implement the PointerBackend protocol

        class ToggleBoolOp(OperationSchema):
            op: Literal[“toggle”] = “toggle”
            path: JSONPointer[JSONBoolean, DotPointer]

        op = ToggleBoolOp(path=”player.isAlive”)
        ```

    Notes:
        Instances are produced by Pydantic validation. If you need direct construction,
        use `JSONPointer.parse()`.
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

        This is exposed for advanced users who provide a custom PointerBackend implementation with additional APIs.
        """
        # TODO: Somehow 'Any' to the actual JSON Pointer class they pass in.
        # Choice: expose ptr as the user's custom PointerBackend for stronger type inferencing.
        # Why: This library only needs the PointerBackend Protocol, if some users want a custom
        #      PointerBackend, then expose that richer API to those users at type-checker time.
        return self._ptr

    @property
    def parts(self) -> Sequence[str]:
        """A sequence of unescaped pointer components."""
        return self._ptr.parts

    @property
    def type_param(self) -> TypeForm[T_co]:
        """The type parameter `T` used to validate reads and writes."""
        return self._type

    @property
    def _adapter(self) -> TypeAdapter[T_co]:
        """The cached Pydantic adapter used for strict `T` validation."""
        return _cached_adapter(self._type)

    @property
    def parent_ptr(self) -> P_co:  # NOTE: add parent property for JSONPointer of parent
        """The underlying pointer instance for this pointer's parent path. Exposed for advanced users along with `ptr`."""
        return _parent_ptr_of(self._ptr)

    # doc is required because custom backends may not use "" as the root token;
    # the backend itself determines what counts as root given the document.
    def is_root(self, doc: JSONValue) -> bool:
        """
        Check whether this pointer resolves to the document root.

        Arguments:
            doc: JSON document to resolve against.

        Returns:
            `True` if this pointer resolves to the root of `doc`, `False` otherwise.
        """
        return _is_root_ptr(self._ptr, doc)

    @classmethod
    def _validator(
        cls,
        path: str | PointerBackend,
        *,
        type_param: TypeForm[Any],
        concrete_backend: type[PointerBackend] | TypeVar,
    ) -> Self:
        """
        Normalize a raw pointer input into a validated `JSONPointer`.

        Arguments:
            path: Pointer string, parsed `JSONPointer`, or backend pointer
                instance supplied by Pydantic validation.
            type_param: Already-validated runtime type parameter `T`.
            concrete_backend: Already-validated backend parameter.

        Returns:
            A `JSONPointer` bound to the resolved backend and type parameter.

        Raises:
            TypeError: If the backend TypeVar cannot be resolved to a concrete
                backend.
            InvalidJSONPointer: If an existing pointer/backend instance cannot
                be rebound to the required backend.
        """
        resolved_backend = cls._resolve_runtime_backend_param(concrete_backend)
        ptr: PointerBackend
        if isinstance(path, JSONPointer):
            path_str = str(path)
            if resolved_backend is DEFAULT_POINTER_CLS:
                ptr = path._ptr
            elif isinstance(path._ptr, resolved_backend):
                ptr = path._ptr
            else:
                ptr = _pointer_backend_instance(path_str, pointer_cls=resolved_backend)
        elif isinstance(path, str):
            path_str = path
            ptr = _pointer_backend_instance(
                path_str,
                pointer_cls=resolved_backend,
            )
        elif isinstance(path, PointerBackend):
            if isinstance(path, resolved_backend):
                path_str = str(path)
                ptr = path
            else:
                raise InvalidJSONPointer(
                    "JSONPointer backend mismatch: "
                    f"required backend is {resolved_backend.__name__} but field uses "
                    f"{path.__class__.__name__}"
                )
        else:  # pragma: no cover
            assert_never(path)

        # Build it
        obj: Self = str.__new__(cls, path_str)

        # Try to reuse the type parameters (type checkers already enforce covariance)
        if isinstance(path, JSONPointer):
            obj._type = path._type
        else:
            obj._type = type_param

        # Reuse pointer backends when provided directly or via JSONPointer.
        obj._ptr = cast(P_co, ptr)

        return obj

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[Self], handler: GetCoreSchemaHandler
    ) -> cs.CoreSchema:
        """Build the Pydantic core schema for `JSONPointer` validation.

        Arguments:
            source_type: The specialized `JSONPointer[T, Backend]` type being built.
            handler: Pydantic's schema generation handler.

        Returns:
            A Pydantic core schema that validates strings, `JSONPointer` instances, and
            `PointerBackend` instances into a `JSONPointer` bound to `T` and the backend.

        Raises:
            TypeError: If no type parameters are supplied, if the backend
                parameter is not a class or `TypeVar`, or if the type parameter
                is not a valid TypeForm.
        """
        type_param, concrete_backend = cls._parse_pointer_type_args(
            *get_args(source_type)
        )
        validator_function = partial(
            cls._validator,
            type_param=type_param,
            concrete_backend=concrete_backend,
        )
        return cs.no_info_after_validator_function(
            function=validator_function,
            schema=cs.union_schema(
                [
                    cs.is_instance_schema(JSONPointer),
                    cs.str_schema(strict=True),
                    cs.is_instance_schema(PointerBackend),
                ]
            ),
            metadata={  # wire to the json_schema
                "type_param": type_param,
                "pointer_backend_param": concrete_backend,  # NOTE: enable customization
            },
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Build the JSON Schema representation for `JSONPointer`.

        Arguments:
            schema: The Pydantic core schema produced by `__get_pydantic_core_schema__`.
            handler: Pydantic's JSON schema generation handler.

        Returns:
            A JSON Schema dict describing a JSON Pointer string, enriched with
            `x-pointer-type-schema` for the declared type parameter.

        Raises:
            TypeError: If the backend TypeVar cannot be resolved, or if the
                type parameter cannot be adapted.
        """
        pointer_backend: type[PointerBackend]
        pointer_backend_param = schema.get("metadata", {}).get("pointer_backend_param")
        if isinstance(pointer_backend_param, TypeVar):
            pointer_backend = cls._resolve_runtime_backend_param(pointer_backend_param)
        else:
            pointer_backend = pointer_backend_param

        if pointer_backend is DEFAULT_POINTER_CLS:
            pointer_format = "json-pointer"
            pointer_description = "JSON Pointer (RFC 6901) string"
        else:
            pointer_format = "x-json-pointer"
            pointer_description = "JSON Pointer string (custom backend syntax)"

        json_schema = handler(schema)
        json_schema.update(
            {
                "type": "string",
                "format": pointer_format,
                "description": pointer_description,  # NOTE: let it be overridable
            }
        )

        # enrich with json schema of type param
        type_param = schema.get("metadata", {}).get("type_param")
        json_schema["x-pointer-type-schema"] = _cached_adapter(type_param).json_schema()
        return json_schema

    @classmethod
    def _parse_pointer_type_args(
        cls, *args: TypeForm[Any]
    ) -> tuple[TypeForm[Any], type[PointerBackend] | TypeVar]:
        """Validate and unpack the `JSONPointer[T, Backend]` parameter tuple.

        Arguments:
            *args: Generic type arguments from `get_args(source_type)`, e.g.
                `(JSONValue, DotPointer)` for `JSONPointer[JSONValue, DotPointer]`.

        Returns:
            A tuple of (type_param, backend_param): type_param is a validated TypeForm
            and backend_param is a concrete backend class or TypeVar.

        Raises:
            TypeError: If no type parameters are supplied, if the backend
                parameter is not a class or `TypeVar`, or if the type parameter
                is not a valid TypeForm.
        """
        if not args:
            raise TypeError(f"{cls} requires at least one type parameter")
        unverified_typeform = args[0]
        unverified_bound_backend = args[1] if len(args) > 1 else DEFAULT_POINTER_CLS

        backend_param = cls._resolve_backend_type_param(unverified_bound_backend)
        type_param = _validate_typeform(unverified_typeform)

        return type_param, backend_param

    @staticmethod
    def _resolve_backend_type_param(
        backend_param: object,
    ) -> type[PointerBackend] | TypeVar:
        """
        Validate the backend generic argument before runtime resolution.

        Arguments:
            backend_param: Raw second generic argument from
                `JSONPointer[T, Backend]`.

        Returns:
            A backend class or unresolved `TypeVar`.

        Raises:
            TypeError: If the backend argument is neither a class nor a
                `TypeVar`, or if the backend class is abstract.
        """
        if isinstance(backend_param, TypeVar):
            return backend_param
        if not isinstance(backend_param, type):
            raise TypeError(
                f"JSONPointer backend parameter {backend_param!r} must be a class or TypeVar"
            )
        if isabstract(backend_param):
            raise TypeError(
                f"JSONPointer backend parameter {backend_param!r} is abstract and cannot be used as a backend"
            )
        return cast(type[PointerBackend], backend_param)

    @classmethod
    def _resolve_runtime_backend_param(
        cls,
        backend_param: type[PointerBackend] | TypeVar,
    ) -> type[PointerBackend]:
        """
        Resolve a backend parameter to a concrete runtime backend class.

        Arguments:
            backend_param: Backend class or backend `TypeVar`.

        Returns:
            A concrete `PointerBackend` class.

        Raises:
            TypeError: If an unspecialized backend `TypeVar` cannot be resolved
                to a concrete default backend.
        """
        if not isinstance(backend_param, TypeVar):
            return backend_param
        return cls._resolve_runtime_backend_typevar(backend_param)

    @classmethod
    def _resolve_runtime_backend_typevar(
        cls,
        backend_typevar: TypeVar,
    ) -> type[PointerBackend]:
        """
        Resolve an unspecialized backend `TypeVar` using its default.

        Arguments:
            backend_typevar: Backend `TypeVar` from the generic parameter list.

        Returns:
            A concrete `PointerBackend` class.

        Raises:
            TypeError: If the `TypeVar` has no usable default backend.
        """
        # Only TypeVar defaults are used for unspecialized backend TypeVars.
        try:
            has_default = backend_typevar.has_default()
        except AttributeError:  # Py3.12
            has_default = False
        if has_default:
            default_candidate = getattr(backend_typevar, "__default__")
            default_backend = cls._coerce_runtime_backend_candidate(default_candidate)
            if default_backend is not None:
                return default_backend

        raise TypeError(
            "JSONPointer backend TypeVar must define a default backend "
            "or be specialized with a concrete backend type"
        )

    @classmethod
    def _coerce_runtime_backend_candidate(
        cls,
        candidate: object,
    ) -> type[PointerBackend] | None:
        """
        Coerce a potential default backend candidate into a usable class.

        Arguments:
            candidate: Runtime object drawn from a backend `TypeVar` default.

        Returns:
            A concrete `PointerBackend` class, or `None` if the candidate is
            not usable as a runtime backend.

        Raises:
            TypeError: If `candidate` is a `TypeVar` with no usable default.
        """
        if isinstance(candidate, TypeVar):
            return cls._resolve_runtime_backend_typevar(candidate)
        if not isinstance(candidate, type):
            return None
        if candidate is PointerBackend or isabstract(candidate):
            return None
        return candidate

    def _validate_target(self, target: object) -> T_co:
        """
        Validate a resolved target value against this pointer's type.

        Arguments:
            target: Candidate value to validate strictly against `T`.

        Returns:
            The validated value, typed as `T`.

        Raises:
            PatchConflictError: If `target` does not conform to `T`.
        """
        try:
            return self._adapter.validate_python(target, strict=True)
        except ValidationError as e:
            raise PatchConflictError(
                f"expected target type {self.type_param} for pointer {str(self)!r}, got: {type(target)}"
            ) from e

    def _validate_replacement(self, value: object) -> JSONValue:
        """
        Validate a replacement value for pointer-backed mutation.

        Arguments:
            value: Candidate value to write at this pointer.

        Returns:
            A strictly validated JSON value.

        Raises:
            PatchConflictError: If `value` does not conform to this pointer's
                type parameter or is not a valid `JSONValue`.
        """
        value_T = self._validate_target(target=value)
        try:
            return _validate_JSONValue(value_T)
        except ValidationError as e:
            raise PatchConflictError(f"value {value!r} is not a valid JSONValue") from e

    # Constructor - for convenience

    @overload
    @classmethod
    def parse(
        cls,
        path: str | PointerBackend,
        *,
        backend: type[P_parse] | None = None,
    ) -> "JSONPointer[JSONValue, P_parse]": ...

    @overload
    @classmethod
    def parse(
        cls,
        path: str | PointerBackend,
        *,
        type_param: TypeForm[T_parse],
        backend: type[P_parse] | None = None,
    ) -> "JSONPointer[T_parse, P_parse]": ...

    @classmethod
    def parse(
        cls,
        path: str | PointerBackend,
        *,
        type_param: TypeForm[Any] | object = _Nothing,
        backend: type[PointerBackend] | None = None,
    ) -> "JSONPointer[Any, PointerBackend]":
        """
        Construct a JSONPointer instance directly, outside of Pydantic models.

        Arguments:
            path: A pointer string, parsed pointer, or pointer backend instance.
            type_param: The type that is enforced on reads and writes.
            backend: The backend pointer implementation. If `None`, defaults to `DEFAULT_POINTER_CLS` (RFC 6901).

        Returns:
            pointer: A validated `JSONPointer` instance.

        Raises:
            TypeError: If the `backend` argument is not a class or `TypeVar`,
                if a backend `TypeVar` cannot be resolved to a concrete backend,
                if the type parameter is not a valid TypeForm, or if `path` is
                not a `str`, `JSONPointer`, or `PointerBackend` instance.
            InvalidJSONPointer: If `path` is not a valid pointer string.

        ??? Acknowledment
            The `type_param` argument places the covariant type parameter `T` in an input position,
            which is technically unsound. But the intended use case of this classmethod is testing
            and ad-hoc pointer construction, where the ergonomics of direct construction outweigh
            the theoretical unsoundness.
        """
        if not isinstance(path, (str, PointerBackend)):
            raise TypeError(
                f"path must be a str or a PointerBackend instance; got {type(path).__name__!r}"
            )

        resolved_type_param = (
            JSONValue if type_param is _Nothing else cast(TypeForm[Any], type_param)
        )

        pointer_args: tuple[TypeForm[Any], ...]
        if backend is None:
            pointer_args = (resolved_type_param,)
        else:
            pointer_args = (resolved_type_param, backend)
        validated_type, validated_backend = cls._parse_pointer_type_args(*pointer_args)

        if backend is None:
            adapter = _cached_adapter(
                JSONPointer[validated_type]  # type: ignore[valid-type]
            )
        else:
            adapter = _cached_adapter(
                JSONPointer[validated_type, validated_backend]  # type: ignore[valid-type]
            )
        try:
            return adapter.validate_python(path)
        except ValidationError as e:
            raise InvalidJSONPointer(f"Invalid pointer: {e}") from e

    # Parse-time helpers

    def is_parent_of(self, other: str) -> bool:
        """
        Check whether this pointer is a strict parent of `other`.

        Arguments:
            other: A `JSONPointer` or pointer string. Strings are parsed using
                this pointer's backend syntax.

        Returns:
            `True` if this pointer is a strict prefix of `other`, `False` otherwise.
            Root is a parent of all paths except itself.

        Raises:
            TypeError: If `other` is a `JSONPointer` with an incompatible backend,
                or a string that cannot be parsed with this pointer's backend.
        """
        if isinstance(other, JSONPointer) and not isinstance(
            other._ptr, type(self._ptr)
        ):
            raise TypeError(
                f"Other pointer {other._ptr!r} has incompatible backend with {self!r}"
            )
        try:
            other_ptr = _pointer_backend_instance(
                other, pointer_cls=self._ptr.__class__
            )
        except InvalidJSONPointer as e:
            raise TypeError(
                f"Invalid pointer string for {self._ptr.__class__.__name__}: {e}"
            ) from e

        # Strict parentage only
        if self == str(other_ptr):
            return False

        return other_ptr.parts[: len(self.parts)] == self.parts

    def is_child_of(self, other: str) -> bool:
        """
        Check whether this pointer is a strict child of `other`.

        Arguments:
            other: A `JSONPointer` or pointer string. Strings are parsed using
                this pointer's backend syntax.

        Returns:
            `True` if `other` is a strict prefix of this pointer, `False` otherwise.
            Root is a parent of all paths except itself.

        Raises:
            TypeError: If `other` is a `JSONPointer` with an incompatible backend,
                or a string that cannot be parsed with this pointer's backend.
        """
        if isinstance(other, JSONPointer) and not isinstance(
            other._ptr, type(self._ptr)
        ):
            raise TypeError(
                f"Other pointer {other._ptr!r} has incompatible backend with {self!r}"
            )
        try:
            other_ptr = _pointer_backend_instance(
                other, pointer_cls=self._ptr.__class__
            )
        except InvalidJSONPointer as e:
            raise TypeError(
                f"Invalid pointer string for {self._ptr.__class__.__name__}: {e}"
            ) from e

        # Strict parentage only
        if self == str(other_ptr):
            return False

        return self.parts[: len(other_ptr.parts)] == other_ptr.parts

    # Runtime helpers

    def is_valid_type(self, target: object) -> bool:
        """
        Check whether `target` conforms to this pointer's type parameter `T`.

        Arguments:
            target: Candidate value to validate.

        Returns:
            `True` if `target` validates strictly against `T`, `False` otherwise.
        """
        try:
            self._adapter.validate_python(target, strict=True)
            return True
        except ValidationError:
            return False

    def get(self, doc: JSONValue) -> T_co:
        """
        Resolve this pointer against `doc` and return the target value (type-gated).

        Arguments:
            doc: JSON document to resolve against.

        Returns:
            The resolved value, validated against `T`.

        Raises:
            PatchConflictError: If the target does not exist, or it is not type `T`.
        """
        # Choice: always defer to the PointerBackend implementation for pointer resolution.
        # Why: Don't reinvent the wheel (and maintain it). Plus, give more power to custom PointerBackends.
        try:
            target = self._ptr.resolve(doc)
        except Exception as e:
            raise PatchConflictError(f"path {str(self)!r} not found: {e}") from e
        val = self._validate_target(target)
        return val

    def is_gettable(self, doc: JSONValue) -> bool:
        """
        Check whether `get(doc)` would succeed.

        Arguments:
            doc: JSON document to resolve against.

        Returns:
            `True` if the pointer resolves to an existing value of type `T`, `False` otherwise.
        """
        try:
            self.get(doc)
        except PatchConflictError:
            return False
        else:
            return True

    def add(self, doc: JSONValue, value: object) -> JSONValue:
        """
        RFC 6902 add (type-gated).

        Arguments:
            doc: JSON document to add to.
            value: Value to add at this path. Must conform to `T` and to `JSONValue`.

        Returns:
            The updated JSON document.

        Raises:
            PatchConflictError: If the target does not exist, if the target is not type `T`,
                or if the value being added is not type `T`.

        Notes:
            May modify `doc` in place; always use the return value. Root-targeting
            operations replace the document and return the new root rather than mutating it.
        """
        target = self._validate_replacement(value)

        match classify_state(self._ptr, doc):
            case TargetState.ROOT:
                self._validate_target(doc)
                return target
            case TargetState.PARENT_NOT_FOUND:
                raise PatchConflictError(
                    f"cannot add value at {str(self)!r} because parent does not exist"
                )
            case TargetState.PARENT_NOT_CONTAINER:
                raise PatchConflictError(
                    f"cannot add value at {str(self)!r} because parent is not a container"
                )
            case TargetState.ARRAY_INDEX_APPEND | TargetState.ARRAY_INDEX_AT_END:
                array = cast(JSONArray[JSONValue], self.parent_ptr.resolve(doc))
                array.append(target)
                return doc
            case TargetState.ARRAY_INDEX_OUT_OF_RANGE:
                raise PatchConflictError(
                    f"cannot add value at {str(self)!r} because array index {self.parts[-1]!r} is out of range"
                )
            case TargetState.OBJECT_KEY_MISSING:
                object = cast(JSONObject[JSONValue], self.parent_ptr.resolve(doc))
                key = self.parts[-1]
                object[key] = target
                return doc
            case (
                TargetState.ARRAY_KEY_INVALID
                | TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX
            ):
                raise PatchConflictError(
                    f"cannot add value at {str(self)!r} because key {self.parts[-1]!r} is an invalid array index"
                )
            case TargetState.VALUE_PRESENT:
                container = cast(JSONContainer[JSONValue], self.parent_ptr.resolve(doc))
                token = self.parts[-1]
                if _is_object(container):
                    self._validate_target(container[token])
                    container[token] = target
                    return doc
                else:
                    container.insert(int(token), target)
                    return doc
            case _ as unreachable:
                assert_never(unreachable)

    def is_addable(
        self,
        doc: JSONValue,
        value: object = _Nothing,
    ) -> bool:
        """
        Check whether RFC 6902 `add` would succeed for this document.

        Arguments:
            doc: JSON document to add to.
            value: Optional value that would be written at this pointer. When
                provided, it must conform to `T` and to `JSONValue`.

        Returns:
            `True` if add semantics would succeed, `False` otherwise.
        """
        if value is not _Nothing:
            try:
                self._validate_replacement(value)
            except PatchConflictError:
                return False

        match classify_state(self._ptr, doc):
            case TargetState.ROOT:
                return self.is_valid_type(doc)
            case TargetState.VALUE_PRESENT:
                container = cast(JSONContainer[JSONValue], self.parent_ptr.resolve(doc))
                token = self.parts[-1]
                if _is_object(container):
                    return self.is_valid_type(container[token])
                return True  # list insert always valid
            case (
                TargetState.ARRAY_INDEX_APPEND
                | TargetState.ARRAY_INDEX_AT_END
                | TargetState.OBJECT_KEY_MISSING
            ):
                return True
            case _:
                return False

    def remove(self, doc: JSONValue) -> JSONValue:
        """
        RFC 6902 remove (type-gated).

        Arguments:
            doc: JSON document to remove from.

        Returns:
            The updated JSON document.

        Raises:
            PatchConflictError: If the target does not exist, or it is not type `T`.

        Notes:
            Modifies `doc` in place; always use the return value.
        """
        match classify_state(self._ptr, doc):
            case TargetState.ROOT:
                self._validate_target(doc)
                raise PatchConflictError("cannot delete the document")
            case TargetState.PARENT_NOT_FOUND:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because parent does not exist"
                )
            case TargetState.PARENT_NOT_CONTAINER:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because parent is not a container"
                )
            case TargetState.ARRAY_INDEX_APPEND:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because '-' indicates append position"
                )
            case TargetState.ARRAY_INDEX_OUT_OF_RANGE | TargetState.ARRAY_INDEX_AT_END:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because array index {self.parts[-1]!r} is out of range"
                )
            case TargetState.OBJECT_KEY_MISSING:
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because key {self.parts[-1]!r} is missing from object"
                )
            case (
                TargetState.ARRAY_KEY_INVALID
                | TargetState.VALUE_PRESENT_AT_NEGATIVE_ARRAY_INDEX
            ):
                raise PatchConflictError(
                    f"cannot remove value at {str(self)!r} because key {self.parts[-1]!r} is an invalid array index"
                )
            case TargetState.VALUE_PRESENT:
                container = cast(JSONContainer[JSONValue], self.parent_ptr.resolve(doc))
                token = self.parts[-1]
                key = int(token) if _is_array(container) else token
                self._validate_target(container[key])  # type: ignore[index]
                del container[key]  # type: ignore[arg-type]
                return doc
            case _ as unreachable:
                assert_never(unreachable)

    def is_removable(self, doc: JSONValue) -> bool:
        """
        Check whether RFC 6902 `remove` would succeed for this document.

        Arguments:
            doc: JSON document to remove from.

        Returns:
            `True` if remove semantics would succeed, `False` otherwise.
        """
        return self.is_gettable(doc) and not self.is_root(doc)

    @override
    def __repr__(self) -> str:
        """Return `ClassName[T]('pointer_string')` representation."""
        type_repr = (
            self._type.__name__ if isinstance(self._type, type) else repr(self._type)
        )
        return f"{self.__class__.__name__}[{type_repr}]({str(self)!r})"
