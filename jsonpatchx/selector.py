from __future__ import annotations

import copy
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
    DEFAULT_SELECTOR_CLS,
    PointerBackend,
    SelectorBackend,
    _selector_backend_instance,
)
from jsonpatchx.exceptions import (
    InvalidJSONSelector,
    PatchConflictError,
)
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.types import (
    JSONBound,
    JSONValue,
    _cached_adapter,
    _validate_JSONValue,
    _validate_typeform,
)

_Nothing = object()
T_co = TypeVar("T_co", bound=JSONBound, covariant=True)
S_co = TypeVar(
    "S_co", bound=SelectorBackend, covariant=True, default=DEFAULT_SELECTOR_CLS
)
T_parse = TypeVar("T_parse", bound=JSONBound)
S_parse = TypeVar("S_parse", bound=SelectorBackend, default=DEFAULT_SELECTOR_CLS)


@final
class JSONSelector(str, Generic[T_co, S_co]):
    """
    A typed query selector with Pydantic integration.

    `JSONSelector[T]` is the query analogue of `JSONPointer[T]`:
    it parses a selector string up front, keeps the parsed backend around, and
    enforces the type parameter `T` when matches are exercised. The string value
    is the selector query itself, so `JSONSelector` is accepted wherever `str` is.

    Unlike `JSONPointer`, a selector can match many locations; mutation resolves
    each match into an exact `JSONPointer` and delegates to pointer mutation rules.

    Notes:
        Instances are produced by Pydantic validation. If you need direct
        construction, use `JSONSelector.parse()`.
    """

    __slots__ = ("_selector", "_type")

    _selector: S_co
    _type: TypeForm[T_co]

    @property
    def ptr(self) -> S_co:
        """
        The underlying selector backend instance.

        This is exposed for advanced users who provide a custom SelectorBackend implementation with additional APIs.
        """
        return self._selector

    @property
    def type_param(self) -> TypeForm[T_co]:
        """The type parameter `T` used to validate matched targets."""
        return self._type

    @property
    def _adapter(self) -> TypeAdapter[T_co]:
        """The cached Pydantic adapter used for strict `T` validation."""
        return _cached_adapter(cast(Any, self._type))

    @classmethod
    def _validator(
        cls,
        selector: str | SelectorBackend,
        *,
        type_param: TypeForm[Any],
        concrete_backend: type[SelectorBackend] | TypeVar,
    ) -> Self:
        """
        Normalize a raw selector input into a validated `JSONSelector`.

        Arguments:
            selector: Selector string, parsed `JSONSelector`, or backend
                selector instance supplied by Pydantic validation.
            type_param: Already-validated runtime type parameter `T`.
            concrete_backend: Already-validated backend parameter.

        Returns:
            A `JSONSelector` bound to the resolved backend and type parameter.

        Raises:
            TypeError: If the backend TypeVar cannot be resolved to a concrete
                backend.
            InvalidJSONSelector: If an existing selector/backend instance
                cannot be rebound to the required backend.
        """
        resolved_backend = cls._resolve_runtime_backend_param(concrete_backend)
        compiled: SelectorBackend
        if isinstance(selector, JSONSelector):
            selector_str = str(selector)
            if resolved_backend is DEFAULT_SELECTOR_CLS:
                compiled = selector._selector
            elif isinstance(selector._selector, resolved_backend):
                compiled = selector._selector
            else:
                compiled = _selector_backend_instance(
                    selector_str,
                    selector_cls=resolved_backend,
                )
        elif isinstance(selector, str):
            selector_str = selector
            compiled = _selector_backend_instance(
                selector_str,
                selector_cls=resolved_backend,
            )
        elif isinstance(selector, SelectorBackend):
            if isinstance(selector, resolved_backend):
                selector_str = str(selector)
                compiled = selector
            else:
                raise InvalidJSONSelector(
                    "JSONSelector backend mismatch: "
                    f"required backend is {resolved_backend.__name__} but field uses "
                    f"{selector.__class__.__name__}"
                )
        else:  # pragma: no cover
            assert_never(selector)

        obj: Self = str.__new__(cls, selector_str)
        obj._type = selector._type if isinstance(selector, JSONSelector) else type_param
        obj._selector = cast(S_co, compiled)
        return obj

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type[Self], handler: GetCoreSchemaHandler
    ) -> cs.CoreSchema:
        """Build the Pydantic core schema for `JSONSelector` validation.

        Arguments:
            source_type: The specialized `JSONSelector[T, Backend]` type being built.
            handler: Pydantic's schema generation handler.

        Returns:
            A Pydantic core schema that validates strings, `JSONSelector` instances, and
            `SelectorBackend` instances into a `JSONSelector` bound to `T` and the backend.

        Raises:
            TypeError: If no type parameters are supplied, if the backend
                parameter is not a class or `TypeVar`, or if the type parameter
                is not a valid TypeForm.
        """
        type_param, concrete_backend = cls._parse_selector_type_args(
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
                    cs.is_instance_schema(JSONSelector),
                    cs.str_schema(strict=True),
                    cs.is_instance_schema(SelectorBackend),
                ]
            ),
            metadata={  # wire to the json_schema
                "type_param": type_param,
                "selector_backend_param": concrete_backend,  # NOTE: enable customization
            },
        )

    @classmethod
    def __get_pydantic_json_schema__(
        cls, schema: cs.CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Build the JSON Schema representation for `JSONSelector`.

        Arguments:
            schema: The Pydantic core schema produced by `__get_pydantic_core_schema__`.
            handler: Pydantic's JSON schema generation handler.

        Returns:
            A JSON Schema dict describing a JSON selector string, enriched with
            `x-selector-type-schema` for the declared type parameter.

        Raises:
            TypeError: If the backend TypeVar cannot be resolved, or if the
                type parameter cannot be adapted.
        """
        selector_backend: type[SelectorBackend]
        selector_backend_param = schema.get("metadata", {}).get(
            "selector_backend_param"
        )
        if isinstance(selector_backend_param, TypeVar):
            selector_backend = cls._resolve_runtime_backend_param(
                selector_backend_param
            )
        else:
            selector_backend = selector_backend_param

        if selector_backend is DEFAULT_SELECTOR_CLS:
            selector_format = "json-path"
            selector_description = "JSONPath (RFC 9535) string"
        else:
            selector_format = "x-json-selector"
            selector_description = "JSON selector string (custom backend syntax)"

        json_schema = handler(schema)
        json_schema.update(
            {
                "type": "string",
                "format": selector_format,
                "description": selector_description,  # NOTE: let it be overridable
            }
        )

        # enrich with json schema of type param
        type_param = schema.get("metadata", {}).get("type_param")
        json_schema["x-selector-type-schema"] = _cached_adapter(
            type_param
        ).json_schema()
        return json_schema

    @classmethod
    def _parse_selector_type_args(
        cls, *args: TypeForm[Any]
    ) -> tuple[TypeForm[Any], type[SelectorBackend] | TypeVar]:
        """Validate and unpack the `JSONSelector[T, Backend]` parameter tuple.

        Arguments:
            *args: Generic type arguments from `get_args(source_type)`, e.g.
                `(JSONValue, MyBackend)` for `JSONSelector[JSONValue, MyBackend]`.

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
        unverified_backend = args[1] if len(args) > 1 else DEFAULT_SELECTOR_CLS

        backend_param = cls._resolve_backend_type_param(unverified_backend)
        type_param = _validate_typeform(unverified_typeform)

        return type_param, backend_param

    @staticmethod
    def _resolve_backend_type_param(
        backend_param: object,
    ) -> type[SelectorBackend] | TypeVar:
        """
        Validate the backend generic argument before runtime resolution.

        Arguments:
            backend_param: Raw second generic argument from
                `JSONSelector[T, Backend]`.

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
                f"JSONSelector backend parameter {backend_param!r} must be a class or TypeVar"
            )
        if isabstract(backend_param):
            raise TypeError(
                f"JSONSelector backend parameter {backend_param!r} is abstract and cannot be used as a backend"
            )
        return cast(type[SelectorBackend], backend_param)

    @classmethod
    def _resolve_runtime_backend_param(
        cls,
        backend_param: type[SelectorBackend] | TypeVar,
    ) -> type[SelectorBackend]:
        """
        Resolve a backend parameter to a concrete runtime backend class.

        Arguments:
            backend_param: Backend class or backend `TypeVar`.

        Returns:
            A concrete `SelectorBackend` class.

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
    ) -> type[SelectorBackend]:
        """
        Resolve an unspecialized backend `TypeVar` using its default.

        Arguments:
            backend_typevar: Backend `TypeVar` from the generic parameter list.

        Returns:
            A concrete `SelectorBackend` class.

        Raises:
            TypeError: If the `TypeVar` has no usable default backend.
        """
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
            "JSONSelector backend TypeVar must define a default backend "
            "or be specialized with a concrete backend type"
        )

    @classmethod
    def _coerce_runtime_backend_candidate(
        cls,
        candidate: object,
    ) -> type[SelectorBackend] | None:
        """
        Coerce a potential default backend candidate into a usable class.

        Arguments:
            candidate: Runtime object drawn from a backend `TypeVar` default.

        Returns:
            A concrete `SelectorBackend` class, or `None` if the candidate is
            not usable as a runtime backend.

        Raises:
            TypeError: If `candidate` is a `TypeVar` with no usable default,
                propagated from `_resolve_runtime_backend_typevar`.
        """
        if isinstance(candidate, TypeVar):
            return cls._resolve_runtime_backend_typevar(candidate)
        if not isinstance(candidate, type):
            return None
        if candidate is SelectorBackend or isabstract(candidate):
            return None
        return candidate

    def _validate_target(self, target: object) -> T_co:
        """
        Validate a matched target value against this selector's type.

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
                f"expected target type {self.type_param} for selector {str(self)!r}, got: {type(target)}"
            ) from e

    def _validate_replacement(self, value: object) -> JSONValue:
        """
        Validate a replacement value for selector-backed mutation.

        Arguments:
            value: Candidate value that will be written to each matched target.

        Returns:
            A strictly validated JSON value.

        Raises:
            PatchConflictError: If `value` does not conform to the selector's
                type parameter or is not a valid `JSONValue`.
        """
        value_T = self._validate_target(value)
        try:
            return _validate_JSONValue(value_T)
        except ValidationError as e:
            raise PatchConflictError(f"value {value!r} is not a valid JSONValue") from e

    @overload
    @classmethod
    def parse(
        cls,
        selector: str | SelectorBackend,
        *,
        backend: type[S_parse] | None = None,
    ) -> "JSONSelector[JSONValue, S_parse]": ...

    @overload
    @classmethod
    def parse(
        cls,
        selector: str | SelectorBackend,
        *,
        type_param: TypeForm[T_parse],
        backend: type[S_parse] | None = None,
    ) -> "JSONSelector[T_parse, S_parse]": ...

    @classmethod
    def parse(
        cls,
        selector: str | SelectorBackend,
        *,
        type_param: TypeForm[Any] | object = _Nothing,
        backend: type[SelectorBackend] | None = None,
    ) -> "JSONSelector[Any, SelectorBackend]":
        """
        Parse a selector string or instance using Pydantic validation.

        Arguments:
            selector: Selector string, parsed selector, or selector backend
                instance.
            type_param: The type that is enforced on matched values.
            backend: The backend selector implementation. If `None`, defaults to `DEFAULT_SELECTOR_CLS` (RFC 9535).

        Returns:
            A validated `JSONSelector` instance.

        Raises:
            TypeError: If the `backend` argument is not a class or `TypeVar`,
                if a backend `TypeVar` cannot be resolved to a concrete backend,
                if the type parameter is not a valid TypeForm, or if `selector`
                is not a `str`, `JSONSelector`, or `SelectorBackend` instance.
            InvalidJSONSelector: If `selector` is not a valid selector string.

        ??? Acknowledment
            The `type_param` argument places the covariant type parameter `T` in an input position,
            which is technically unsound. But the intended use case of this classmethod is testing
            and ad-hoc selector construction, where the ergonomics of direct construction outweigh
            the theoretical unsoundness.
        """
        if not isinstance(selector, (str, SelectorBackend)):
            raise TypeError(
                f"selector must be a str or a SelectorBackend instance; got {type(selector).__name__!r}"
            )

        resolved_type_param = (
            JSONValue if type_param is _Nothing else cast(TypeForm[Any], type_param)
        )

        selector_args: tuple[TypeForm[Any], ...]
        if backend is None:
            selector_args = (resolved_type_param,)
        else:
            selector_args = (resolved_type_param, backend)
        validated_type, validated_backend = cls._parse_selector_type_args(
            *selector_args
        )

        if backend is None:
            adapter = _cached_adapter(
                JSONSelector[validated_type]  # type: ignore[valid-type]
            )
        else:
            adapter = _cached_adapter(
                JSONSelector[validated_type, validated_backend]  # type: ignore[valid-type]
            )
        try:
            return adapter.validate_python(selector)
        except ValidationError as e:
            raise InvalidJSONSelector(f"Invalid selector: {e}") from e

    def is_valid_type(self, target: object) -> bool:
        """
        Check whether `target` conforms to this selector's type parameter `T`.

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

    def _pointer_instances(self, doc: JSONValue) -> list[PointerBackend]:
        """
        Resolve this selector and return backend pointer instances.

        Arguments:
            doc: JSON document to resolve against.

        Returns:
            pointer_instances: A list of backend pointer instances for each resolved match.

        Raises:
            PatchConflictError: If the selector backend cannot resolve the
                selector against `doc`.
            TypeError: If the backend yields objects that do not implement `PointerBackend`.
        """
        try:
            raw_pointers = list(self._selector.pointers(doc))
        except Exception as e:
            raise PatchConflictError(
                f"selector {str(self)!r} could not be resolved: {e}"
            ) from e

        pointers: list[PointerBackend] = []
        for pointer in raw_pointers:
            if not isinstance(pointer, PointerBackend):
                raise TypeError(
                    f"selector backend returned invalid pointer {pointer!r}: "
                    f"expected PointerBackend, got {type(pointer).__name__}"
                )
            pointers.append(pointer)
        return pointers

    def get_pointers(self, doc: JSONValue) -> list[JSONPointer[T_co, PointerBackend]]:
        """
        Resolve this selector against `doc` and return exact matched pointers.

        Arguments:
            doc: JSON document to resolve against.

        Returns:
            pointers: Typed `JSONPointer` values for each matched location.

        Raises:
            PatchConflictError: If selector resolution fails.
            TypeError: If the backend yields objects that do not implement `PointerBackend`.
            InvalidJSONPointer: If a resolved backend pointer cannot be parsed into a
                `JSONPointer` (propagated from `JSONPointer.parse`).
        """
        return [
            JSONPointer.parse(
                pointer,
                type_param=self._type,
                backend=type(pointer),
            )
            for pointer in self._pointer_instances(doc)
        ]

    def getall(self, doc: JSONValue) -> list[T_co]:
        """
        Resolve this selector against `doc` and return all matched values.

        Arguments:
            doc: JSON document to resolve against.

        Returns:
            A list of matched values validated against `T`. If the selector
            matches nothing, the list will be empty.

        Raises:
            PatchConflictError: If selector resolution fails or a matched
                pointer cannot be read as type `T`.
            TypeError: If the backend yields objects that do not implement `PointerBackend`.
            InvalidJSONPointer: If a resolved backend pointer cannot be parsed into a
                `JSONPointer`, propagated from `get_pointers`.
        """
        return [pointer.get(doc) for pointer in self.get_pointers(doc)]

    def is_gettable(self, doc: JSONValue) -> bool:
        """
        Check whether `getall(doc)` would succeed.

        Arguments:
            doc: JSON document to resolve against.

        Returns:
            `True` if selector resolution and per-match reads succeed, `False` otherwise.

        Raises:
            TypeError: If the backend yields objects that do not implement `PointerBackend`.
            InvalidJSONPointer: If a resolved backend pointer cannot be parsed into a
                `JSONPointer`, propagated from `get_pointers`.
        """
        try:
            self.getall(doc)
        except PatchConflictError:
            return False
        else:
            return True

    def addall(self, doc: JSONValue, value: object) -> JSONValue:
        """
        Apply RFC 6902-style add semantics at every matched location.

        Arguments:
            doc: JSON document to add to.
            value: Value to write at every matched location. Must conform to `T` and to `JSONValue`.

        Returns:
            The updated JSON document.

        Raises:
            PatchConflictError: If `value` is not valid for this selector, if
                selector resolution fails, or if any matched pointer cannot be
                updated.
            TypeError: If the backend yields objects that do not implement `PointerBackend`.
            InvalidJSONPointer: If a resolved backend pointer cannot be parsed into a
                `JSONPointer`, propagated from `get_pointers`.

        Notes:
            May modify `doc` in place; always use the return value. Root-targeting
            matches replace the document and return the new root rather than mutating it.
        """
        target = self._validate_replacement(value)
        for pointer in self.get_pointers(doc):
            doc = pointer.add(doc, copy.deepcopy(target))
        return doc

    def is_addable(
        self,
        doc: JSONValue,
        value: object = _Nothing,
    ) -> bool:
        """
        Check whether `addall` would succeed for this document.

        Arguments:
            doc: JSON document to add to.
            value: Optional value that would be written to every matched
                location. When omitted, only the current matched targets are
                checked.

        Returns:
            `True` if the selector can be resolved and every matched pointer
            accepts the requested add semantics, `False` otherwise.

        Raises:
            TypeError: If the backend yields objects that do not implement `PointerBackend`.
            InvalidJSONPointer: If a resolved backend pointer cannot be parsed into a
                `JSONPointer`, propagated from `get_pointers`.
        """
        if value is _Nothing:
            try:
                return all(
                    pointer.is_addable(doc) for pointer in self.get_pointers(doc)
                )
            except PatchConflictError:
                return False

        try:
            target = self._validate_replacement(value)
            return all(
                pointer.is_addable(doc, target) for pointer in self.get_pointers(doc)
            )
        except PatchConflictError:
            return False

    def removeall(self, doc: JSONValue) -> JSONValue:
        """
        Apply RFC 6902-style remove semantics at every matched location.

        Arguments:
            doc: JSON document to remove from.

        Returns:
            The updated JSON document.

        Raises:
            PatchConflictError: If selector resolution fails or any matched
                pointer cannot be removed.
            TypeError: If the backend yields objects that do not implement `PointerBackend`.
            InvalidJSONPointer: If a resolved backend pointer cannot be parsed into a
                `JSONPointer`, propagated from `get_pointers`.

        Notes:
            Modifies `doc` in place; always use the return value.
        """
        for pointer in self.get_pointers(doc):
            doc = pointer.remove(doc)
        return doc

    def is_removable(self, doc: JSONValue) -> bool:
        """
        Check whether `removeall` would succeed for this document.

        Arguments:
            doc: JSON document to remove from.

        Returns:
            `True` if the selector resolves and all matched targets are
            removable, `False` otherwise.

        Raises:
            TypeError: If the backend yields objects that do not implement `PointerBackend`.
            InvalidJSONPointer: If a resolved backend pointer cannot be parsed into a
                `JSONPointer`, propagated from `get_pointers`.

        Notes:
            This is intentionally looser than `removeall()`. Selector
            removal does not promise a stable or safety-maximizing order, so
            this predicate checks whether every current match is removable
            under the pointer layer's rules.
        """
        try:
            return all(pointer.is_removable(doc) for pointer in self.get_pointers(doc))
        except PatchConflictError:
            return False

    @override
    def __repr__(self) -> str:
        """Return `ClassName[T]('selector_string')` representation."""
        type_repr = (
            self._type.__name__ if isinstance(self._type, type) else repr(self._type)
        )
        return f"{self.__class__.__name__}[{type_repr}]({str(self)!r})"
