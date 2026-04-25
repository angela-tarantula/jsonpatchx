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
    enforces the type parameter `T` when matches are exercised.

    Query selectors differ from pointers in one important way: they can resolve
    to many locations. So the convenience surface is plural:

    - `getall(doc)` validates and returns every matched value.
    - `addall(doc, value)` validates the current matches and writes to every
      matched location.
    - `removeall(doc)` validates the current matches and removes every matched
      location.

    Mutation is implemented by resolving the selector into exact
    `JSONPointer` locations and delegating to pointer mutation rules. The
    selector backend's `pointers()` output is the source of truth for which
    pointer backend is being used.
    """

    __slots__ = ("_selector", "_type")

    _selector: S_co
    _type: TypeForm[T_co]

    @property
    def ptr(self) -> S_co:
        """
        The underlying selector backend instance.

        This is exposed for advanced users who provide a custom
        `SelectorBackend` with additional APIs.
        """
        return self._selector

    @property
    def type_param(self) -> TypeForm[T_co]:
        """The expected type parameter `T` used to validate matched targets."""
        return self._type

    @property
    def _adapter(self) -> TypeAdapter[T_co]:
        """Return the cached Pydantic adapter used for strict `T` validation."""
        return _cached_adapter(cast(Any, self._type))

    @classmethod
    def _validator(
        cls,
        selector: str | Self | SelectorBackend,
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
        """
        Validate the selector generic arguments.

        Arguments:
            *args: Generic arguments from `JSONSelector[T, Backend]`.

        Returns:
            The validated type parameter and backend parameter.

        Raises:
            TypeError: If the selector is missing its required type argument.
            InvalidJSONSelector: If the type parameter or backend parameter is
                invalid.
        """
        if not args:
            raise TypeError(f"{cls} requires at least one type parameter")
        unverified_typeform = args[0]
        unverified_backend = args[1] if len(args) > 1 else DEFAULT_SELECTOR_CLS

        backend_param = cls._resolve_backend_type_param(unverified_backend)
        type_param = _validate_typeform(unverified_typeform, InvalidJSONSelector)

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
            InvalidJSONSelector: If the backend argument is neither a class nor
                a `TypeVar`.
        """
        if isinstance(backend_param, TypeVar):
            return backend_param
        if not isinstance(backend_param, type):
            raise InvalidJSONSelector(
                f"JSONSelector backend parameter {backend_param!r} must be a class or TypeVar"
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
            InvalidJSONSelector: If an unspecialized backend `TypeVar` cannot
                be resolved to a concrete default backend.
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
            InvalidJSONSelector: If the `TypeVar` has no usable default
                backend.
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

        raise InvalidJSONSelector(
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
        Validate a matched or replacement value against this selector's type.

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
        selector: str | Self | SelectorBackend,
        *,
        backend: type[S_parse] | None = None,
    ) -> "JSONSelector[JSONValue, S_parse]": ...

    @overload
    @classmethod
    def parse(
        cls,
        selector: str | Self | SelectorBackend,
        *,
        type_param: TypeForm[T_parse],
        backend: type[S_parse] | None = None,
    ) -> "JSONSelector[T_parse, S_parse]": ...

    @classmethod
    def parse(
        cls,
        selector: str | Self | SelectorBackend,
        *,
        type_param: TypeForm[Any] | object = _Nothing,
        backend: type[SelectorBackend] | None = None,
    ) -> "JSONSelector[Any, SelectorBackend]":
        """
        Parse a selector string or instance using Pydantic validation.

        Arguments:
            selector: Selector string, parsed selector, or selector backend
                instance.
            type_param: Type enforced when matched values are exercised.
            backend: Optional concrete backend class. When omitted, the built-in
                JSONPath backend is used.

        Returns:
            A validated `JSONSelector` instance.

        Raises:
            InvalidJSONSelector: If the selector string, backend, or generic
                parameters are invalid.

        Notes:
            `type_param` technically places the covariant `T` parameter in an
            input position, which would normally be an unsound public API
            shape. That tradeoff is intentional here because `parse()` is only
            a convenience constructor around Pydantic validation. Normal
            construction happens through Pydantic on an already-specialized
            `JSONSelector[...]` type, so callers are not meant to treat
            `parse()` as the primary semantic surface for consuming `T`.
        """
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
        return adapter.validate_python(selector)

    def is_valid_type(self, target: object) -> bool:
        """
        Return `True` if `target` conforms to this selector's type.

        Arguments:
            target: Candidate value to validate.

        Returns:
            `True` when `target` validates strictly against `T`,
            otherwise `False`.
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
            doc: Target JSON document.

        Returns:
            Backend pointers for each resolved match.

        Raises:
            PatchConflictError: If the selector backend cannot resolve the
                selector against `doc`.
            InvalidJSONSelector: If the backend yields invalid pointer objects.
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
                raise InvalidJSONSelector(
                    f"selector backend returned invalid pointer {pointer!r}"
                )
            pointers.append(pointer)
        return pointers

    def get_pointers(self, doc: JSONValue) -> list[JSONPointer[T_co, PointerBackend]]:
        """
        Resolve this selector against `doc` and return exact matched pointers.

        Arguments:
            doc: Target JSON document.

        Returns:
            Typed `JSONPointer` values for each matched location.

        Raises:
            PatchConflictError: If selector resolution fails.
            InvalidJSONSelector: If the backend yields invalid matches or
                invalid pointer objects.
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
            doc: Target JSON document.

        Returns:
            A list of matched values validated against `T`. If the selector
            matches nothing, the list will be empty.

        Raises:
            PatchConflictError: If selector resolution fails or a matched
                pointer cannot be read as type `T`.
            InvalidJSONSelector: If the backend yields invalid matches or
                invalid pointer data.
        """
        return [pointer.get(doc) for pointer in self.get_pointers(doc)]

    def is_gettable(self, doc: JSONValue) -> bool:
        """
        Return `True` if `getall(doc)` would succeed.

        Arguments:
            doc: Target JSON document.

        Returns:
            `True` if selector resolution and per-match reads succeed,
            otherwise `False`.
        """
        try:
            self.getall(doc)
        except (InvalidJSONSelector, PatchConflictError):
            return False
        else:
            return True

    def addall(self, doc: JSONValue, value: object) -> JSONValue:
        """
        Apply RFC 6902-style add semantics at every matched location.

        Arguments:
            doc: Target JSON document.
            value: Replacement value written to every matched location.

        Returns:
            The updated document.

        Raises:
            PatchConflictError: If `value` is not valid for this selector, if
                selector resolution fails, or if any matched pointer cannot be
                updated.
            InvalidJSONSelector: If the backend yields invalid matches or
                invalid pointer data.
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
        Return `True` if `addall()` would succeed.

        Arguments:
            doc: Target JSON document.
            value: Optional value that would be written to every matched
                location. When omitted, only the current matched targets are
                checked.

        Returns:
            `True` if the selector can be resolved and every matched pointer
            accepts the requested add semantics, otherwise `False`.
        """
        if value is _Nothing:
            try:
                return all(
                    pointer.is_addable(doc) for pointer in self.get_pointers(doc)
                )
            except (InvalidJSONSelector, PatchConflictError):
                return False

        try:
            target = self._validate_replacement(value)
            return all(
                pointer.is_addable(doc, target) for pointer in self.get_pointers(doc)
            )
        except (InvalidJSONSelector, PatchConflictError):
            return False

    def removeall(self, doc: JSONValue) -> JSONValue:
        """
        Apply RFC 6902-style remove semantics at every matched location.

        Arguments:
            doc: Target JSON document.

        Returns:
            The updated document.

        Raises:
            PatchConflictError: If selector resolution fails or any matched
                pointer cannot be removed.
            InvalidJSONSelector: If the backend yields invalid matches or
                invalid pointer data.
        """
        for pointer in self.get_pointers(doc):
            doc = pointer.remove(doc)
        return doc

    def is_removable(self, doc: JSONValue) -> bool:
        """
        Return `True` if all matched targets are removable in principle.

        Arguments:
            doc: Target JSON document.

        Returns:
            `True` if the selector resolves and the current matches are
            gettable/removable targets, otherwise `False`.

        Notes:
            This is intentionally looser than `removeall()`. Selector
            removal does not promise a stable or safety-maximizing order, so
            this predicate only checks the current matches, not whether any
            particular backend iteration order will succeed.
        """
        return self.is_gettable(doc)

    @override
    def __repr__(self) -> str:
        type_repr = (
            self._type.__name__ if isinstance(self._type, type) else repr(self._type)
        )
        return f"{self.__class__.__name__}[{type_repr}]({str(self)!r})"
