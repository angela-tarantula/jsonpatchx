from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from typing import TYPE_CHECKING, Annotated, Any, cast, get_args

from pydantic import Field, TypeAdapter
from pydantic_core import core_schema
from typing_extensions import TypeForm, TypeIs

from jsonpatchx.exceptions import InvalidJSONPointer

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


"""Pydantic-aware JSON types.

Design note:

These definitions look more complicated than the underlying JSON domain because
they are balancing three competing requirements at once:
1. strict runtime validation,
2. clean static types for users and type checkers, and
3. stable/minimal OpenAPI output.

The obvious-looking alternatives all break one of those goals:
- Runtime type / Annotated[..., WithJsonSchema(...)] aliases for
  JSONString / JSONNull / JSONBoolean cause Pydantic to promote
  those aliases into named schema components, which pollutes the generated
  OpenAPI surface with helper types.
- Applying WithJsonSchema({"type": "number"}) to JSONNumber hides
  field-level JSON Schema keywords such as gt / multiple_of because
  it replaces the generated schema instead of refining it.
- Writing Annotated[int | float, Field(strict=True, ...)] for
  JSONNumber does not work: Pydantic cannot apply strict=True to the
  union node itself, so strictness has to be expressed on the individual
  int and float branches.
- Exposing the full internal JSON union for JSONValue creates noisy named
  OpenAPI components for internal helper types that are not part of the public
  contract we want to advertise.

So the "ugly" pattern here is intentional:
- TYPE_CHECKING gets pleasant alias syntax,
- runtime uses tiny helper classes only where Pydantic/OpenAPI need more
  control, and
- validation schema is allowed to differ from published JSON Schema when that
  produces a better external API contract.
"""


def _strict_validator(typeform: TypeForm[Any]) -> core_schema.CoreSchema:
    """
    Build a strict validator for a TypeForm using a cached TypeAdapter.

    This keeps validation strict without exposing the internal helper type's full
    generated JSON Schema.
    """
    adapter = _type_adapter_for(typeform)

    def _validate(value: object) -> object:
        return adapter.validate_python(value, strict=True)

    return core_schema.no_info_plain_validator_function(_validate)


if TYPE_CHECKING:
    type JSONBoolean = bool
    type JSONNumber = int | float
    type JSONString = str
    type JSONNull = None
    type JSONArray[T] = list[T]
    type JSONObject[T] = dict[str, T]
else:

    class JSONBoolean:
        """Strict JSON boolean helper used in Pydantic-backed patch contracts."""

        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            return _strict_validator(Annotated[bool, Field(strict=True)])

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {"type": "boolean"}

    class JSONNumber:
        """Strict JSON number helper accepting ``int`` or finite ``float`` values."""

        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            type _JSONNumberInternal = Annotated[  # NOTE: document the necessity of field strictness. adapters strict too for preventing "2" -> 2 for JSONBoolean and int/float
                Annotated[int, Field(strict=True)]
                | Annotated[float, Field(strict=True, allow_inf_nan=False)],
                Field(
                    description="integer or finite float (no NaN/Infinity).",
                ),
            ]
            return _strict_validator(_JSONNumberInternal)

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {"type": "number"}

    class JSONString:
        """Strict JSON string helper used in operation models and patch schemas."""

        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            return _strict_validator(Annotated[str, Field(strict=True)])

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {"type": "string"}

    class JSONNull:
        """Strict JSON null helper."""

        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            return _strict_validator(Annotated[None, Field()])

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {"type": "null"}

    class JSONArray[T]:
        """Strict JSON array helper restricted to concrete ``list`` values."""

        @classmethod
        def __get_pydantic_core_schema__(
            cls, source_type: object, handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            (item_type,) = get_args(source_type) or (Any,)
            item_schema = handler.generate_schema(item_type)
            return core_schema.list_schema(item_schema, strict=True)

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return handler(_core_schema)

    class JSONObject[T]:
        """Strict JSON object helper restricted to ``dict[str, ...]`` values."""

        @classmethod
        def __get_pydantic_core_schema__(
            cls, source_type: object, handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            (value_type,) = get_args(source_type) or (Any,)
            value_schema = handler.generate_schema(value_type)
            return core_schema.dict_schema(
                core_schema.str_schema(), value_schema, strict=True
            )

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return handler(_core_schema)


type JSONScalar = JSONBoolean | JSONNumber | JSONString | JSONNull
"""Strict JSON scalar helper union."""

type JSONContainer[T] = JSONArray[T] | JSONObject[T]
"""Strict JSON container helper union."""

# type-narrowing helpers
# NOTE: consider making public type-narrowing helpers


def _is_container(value: JSONValue) -> TypeIs[JSONContainer[JSONValue]]:
    """Internal: runtime check for JSON containers (dict/list)."""
    return isinstance(value, (list, dict))


def _is_object(value: JSONValue) -> TypeIs[JSONObject[JSONValue]]:
    return isinstance(value, dict)


def _is_array(value: JSONValue) -> TypeIs[JSONArray[JSONValue]]:
    return isinstance(value, list)


if TYPE_CHECKING:
    # Static typing: keep JSONValue as a strict JSON union.
    type JSONValue = Annotated[
        JSONScalar | JSONContainer[JSONValue],
        Field(),
    ]  # NOTE: document somewhere that you can't do isinstance because these are type aliases
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
else:

    class JSONValue:
        """
        Runtime JSON value type with strict validation and minimal OpenAPI schema.

        Validation delegates to the strict JSON union, while
        JSON schema is deliberately inlined as ``{}`` to avoid a named component.
        """

        @classmethod
        def __get_pydantic_core_schema__(
            cls, _source_type: object, _handler: core_schema.GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            type _JSONValueInternal = Annotated[
                JSONBoolean
                | JSONNumber
                | JSONString
                | JSONNull
                | JSONArray[_JSONValueInternal]
                | JSONObject[_JSONValueInternal],
                Field(),
            ]
            return _strict_validator(_JSONValueInternal)

        @classmethod
        def __get_pydantic_json_schema__(
            cls,
            _core_schema: core_schema.CoreSchema,
            _handler: core_schema.GetJsonSchemaHandler,
        ) -> dict[str, object]:
            return {}


def _validate_JSONValue(obj: object) -> JSONValue:
    return _type_adapter_for(JSONValue).validate_python(obj, strict=True)


def _validate_typeform(unverified: object) -> TypeForm[Any]:
    """Validate a TypeForm parameter."""  # NOTE: move to JSONPointer if it's gonna raise InvalidJSONPointer
    try:
        _type_adapter_for(unverified)  # type: ignore[arg-type]
    except Exception as e:
        raise InvalidJSONPointer(
            f"JSONPointer type parameter {unverified!r} must be a valid TypeForm"
        ) from e
    return cast(TypeForm[Any], unverified)


type JSONBound = JSONScalar | Sequence[JSONBound] | Mapping[str, JSONBound]
"""Bound for recursively JSON-shaped values accepted by generic helpers such as
``JSONPointer[T]``."""
# Use it like ``T = TypeVar("T", default=JSONValue, bound=JSONBound)``
