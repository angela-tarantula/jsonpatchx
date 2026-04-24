from __future__ import annotations

import copy
from functools import partial
from inspect import isabstract
from typing import Any, Generic, Self, assert_never, cast, final, get_args, override

from pydantic import GetCoreSchemaHandler, GetJsonSchemaHandler, TypeAdapter
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import core_schema as cs
from typing_extensions import TypeForm, TypeVar

from jsonpatchx.backend import (
    _DEFAULT_SELECTOR_CLS,
    PointerBackend,
    SelectorBackend,
    SelectorMatch,
    _selector_backend_instance,
)
from jsonpatchx.exceptions import (
    InvalidJSONPointer,
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
    "S_co", bound=SelectorBackend, covariant=True, default=_DEFAULT_SELECTOR_CLS
)


@final
class JSONSelector(str, Generic[T_co, S_co]):
    """
    A typed query selector with Pydantic integration.

    ``JSONSelector[T]`` is the query analogue of ``JSONPointer[T]``:
    it parses a selector string up front, keeps the parsed backend around, and
    enforces the type parameter ``T`` when matches are exercised.

    Query selectors differ from pointers in one important way: they can resolve
    to many locations. So the convenience surface is plural:

    - ``getall(doc)`` validates and returns every matched value.
    - ``addall(doc, value)`` validates the current matches and writes to every
      matched location.
    - ``removeall(doc)`` validates the current matches and removes every matched
      location.

    Mutation is implemented by converting each match into an exact
    ``JSONPointer`` and delegating to pointer mutation rules. Each match's
    ``pointer()`` result is the source of truth for which pointer backend is
    being used.
    """

    __slots__ = ("_selector", "_type")

    _selector: S_co
    _type: TypeForm[T_co]

    @property
    def ptr(self) -> S_co:
        """
        The underlying selector backend instance.

        This is exposed for advanced users who provide a custom
        ``SelectorBackend`` with additional APIs.
        """
        return self._selector

    @property
    def type_param(self) -> TypeForm[T_co]:
        """The expected type parameter ``T`` used to validate matched targets."""
        return self._type

    @property
    def _adapter(self) -> TypeAdapter[T_co]:
        return _cached_adapter(cast(Any, self._type))

    @classmethod
    def _validator(
        cls,
        selector: str | Self | SelectorBackend,
        *,
        type_param: TypeForm[Any],
        concrete_backend: type[SelectorBackend] | TypeVar,
    ) -> Self:
        resolved_backend = cls._resolve_runtime_backend_param(concrete_backend)
        compiled: SelectorBackend
        if isinstance(selector, JSONSelector):
            selector_str = str(selector)
            if resolved_backend is _DEFAULT_SELECTOR_CLS:
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
        selector_backend_param = schema["metadata"]["selector_backend_param"]
        if isinstance(selector_backend_param, TypeVar):
            selector_backend = cls._resolve_runtime_backend_param(
                selector_backend_param
            )
        else:
            selector_backend = selector_backend_param

        if selector_backend is _DEFAULT_SELECTOR_CLS:
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
        type_param = schema["metadata"]["type_param"]
        json_schema["x-selector-type-schema"] = _cached_adapter(
            type_param
        ).json_schema()
        return json_schema

    @classmethod
    def _parse_selector_type_args(
        cls, *args: TypeForm[Any]
    ) -> tuple[TypeForm[Any], type[SelectorBackend] | TypeVar]:
        if not args:
            raise TypeError(f"{cls} requires at least one type parameter")
        unverified_typeform = args[0]
        unverified_backend = args[1] if len(args) > 1 else _DEFAULT_SELECTOR_CLS

        backend_param = cls._resolve_backend_type_param(unverified_backend)
        type_param = _validate_typeform(unverified_typeform, InvalidJSONSelector)

        return type_param, backend_param

    @staticmethod
    def _resolve_backend_type_param(
        backend_param: object,
    ) -> type[SelectorBackend] | TypeVar:
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
        if not isinstance(backend_param, TypeVar):
            return backend_param
        return cls._resolve_runtime_backend_typevar(backend_param)

    @classmethod
    def _resolve_runtime_backend_typevar(
        cls,
        backend_typevar: TypeVar,
    ) -> type[SelectorBackend]:
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
        if isinstance(candidate, TypeVar):
            return cls._resolve_runtime_backend_typevar(candidate)
        if not isinstance(candidate, type):
            return None
        if candidate is SelectorBackend or isabstract(candidate):
            return None
        return candidate

    def _validate_target(self, target: object) -> T_co:
        try:
            return self._adapter.validate_python(target, strict=True)
        except Exception as e:
            raise PatchConflictError(
                f"expected target type {self.type_param} for selector {str(self)!r}, got: {type(target)}"
            ) from e

    @classmethod
    def parse(
        cls,
        selector: str | Self | SelectorBackend,
        *,
        type_param: TypeForm[Any] = JSONValue,
        backend: type[SelectorBackend] | None = None,
    ) -> Self:
        """
        Parse a selector string or instance using Pydantic validation.

        This is a convenience wrapper around ``TypeAdapter(JSONSelector[...])``.
        """
        selector_args: tuple[TypeForm[Any], ...]
        if backend is None:
            selector_args = (type_param,)
        else:
            selector_args = (type_param, backend)
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
        try:
            self._adapter.validate_python(target, strict=True)
            return True
        except Exception:
            return False

    def _raw_matches(self, doc: JSONValue) -> list[SelectorMatch]:
        try:
            raw_matches = list(self._selector.finditer(doc))
        except Exception as e:
            raise PatchConflictError(
                f"selector {str(self)!r} could not be resolved: {e}"
            ) from e

        matches: list[SelectorMatch] = []
        for match in raw_matches:
            if not isinstance(match, SelectorMatch):
                raise InvalidJSONSelector(
                    f"selector backend returned invalid match {match!r}"
                )
            matches.append(match)
        return matches

    def _get_pointer_instance(self, match: SelectorMatch) -> PointerBackend:
        raw_pointer = match.pointer()
        if not isinstance(raw_pointer, PointerBackend):
            raise InvalidJSONSelector(
                f"selector backend returned invalid match {match!r}: pointer() must return PointerBackend"
            )
        return raw_pointer

    def _pointer_instances(self, doc: JSONValue) -> list[PointerBackend]:
        return [self._get_pointer_instance(match) for match in self._raw_matches(doc)]

    def get_pointers(self, doc: JSONValue) -> list[JSONPointer[T_co, PointerBackend]]:
        """
        Resolve this selector against ``doc`` and return exact matched pointers.

        This exposes the matched locations as typed ``JSONPointer`` values, so
        callers can use familiar pointer utilities case by case.
        """
        json_pointers: list[JSONPointer[T_co, PointerBackend]] = []
        for pointer in self._pointer_instances(doc):
            pointer_backend = type(pointer)
            try:
                json_pointers.append(
                    JSONPointer.parse(
                        pointer,
                        type_param=cast(Any, self._type),
                        backend=pointer_backend,
                    )
                )
            except InvalidJSONPointer as e:
                raise InvalidJSONSelector(
                    f"selector match pointer {pointer!r} is incompatible with backend {pointer_backend.__name__}"
                ) from e
        return json_pointers

    def getall(self, doc: JSONValue) -> list[T_co]:
        """
        Resolve this selector against ``doc`` and return all matched values.

        Every matched pointer is exercised through ``JSONPointer.get()``, so the
        selector's type parameter ``T`` is enforced at read time. If the
        selector matches nothing, this returns an empty list.
        """
        return [pointer.get(doc) for pointer in self.get_pointers(doc)]

    def is_gettable(self, doc: JSONValue) -> bool:
        try:
            self.getall(doc)
        except Exception:
            return False
        else:
            return True

    def addall(self, doc: JSONValue, value: object) -> JSONValue:
        """
        Apply RFC 6902-style add semantics at every matched location.

        JsonPatchX currently applies matched pointers one at a time after
        resolving them, but callers should not rely on any specific ordering or
        extra overlap guarantees beyond ordinary pointer semantics.
        """
        # Validate up front in case there are no matches to trigger pointer-level validation
        value_T: T_co = self._validate_target(value)
        try:
            target = _validate_JSONValue(value_T)
        except Exception as e:
            raise PatchConflictError(f"value {value!r} is not a valid JSONValue") from e

        for pointer in self.get_pointers(doc):
            doc = pointer.add(doc, copy.deepcopy(target))
        return doc

    def is_addable(
        self,
        doc: JSONValue,
        value: object = _Nothing,
    ) -> bool:
        if value is _Nothing:
            try:
                return all(
                    pointer.is_addable(doc) for pointer in self.get_pointers(doc)
                )
            except Exception:
                return False

        try:
            # Validate up front in case there are no matches to trigger pointer-level validation
            value_T: T_co = self._validate_target(value)
            target = _validate_JSONValue(value_T)

            return all(
                pointer.is_addable(doc, target) for pointer in self.get_pointers(doc)
            )
        except Exception:
            return False

    def removeall(self, doc: JSONValue) -> JSONValue:
        """
        Apply RFC 6902-style remove semantics at every matched location.

        JsonPatchX currently applies matched pointers one at a time after
        resolving them, but callers should not rely on any specific ordering or
        extra overlap guarantees beyond ordinary pointer semantics.
        """
        for pointer in self.get_pointers(doc):
            doc = pointer.remove(doc)
        return doc

    def is_removable(self, doc: JSONValue) -> bool:
        """
        Return True if all matched targets are currently removable in principle.

        This is intentionally looser than ``removeall()``: selector removal
        does not promise a stable or safety-maximizing order, so this predicate
        only checks whether the current matches are gettable/removable targets,
        not whether the backend's present iteration order will succeed.
        """
        return self.is_gettable(doc)

    @override
    def __repr__(self) -> str:
        type_repr = (
            self._type.__name__ if isinstance(self._type, type) else repr(self._type)
        )
        return f"{self.__class__.__name__}[{type_repr}]({str(self)!r})"
