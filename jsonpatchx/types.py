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


def _cached_adapter[T](expected: TypeForm[T]) -> TypeAdapter[T]:
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
    adapter = _cached_adapter(typeform)

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
        """Strict JSON boolean. For type checkers: `bool`."""

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
        """Strict JSON number. For type checkers: `int | float` (strict; finite floats only, no `NaN` or `Infinity`)."""

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
        """Strict JSON string. For type checkers: `str`."""

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
        """Strict JSON null. For type checkers: `None`."""

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
        """Strict JSON array. For type checkers: `list[T]`."""

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
        """Strict JSON object. For type checkers: `dict[str, T]`."""

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
"""Strict JSON scalar. For type checkers: `JSONBoolean | JSONNumber | JSONString | JSONNull`."""

type JSONContainer[T] = JSONArray[T] | JSONObject[T]
"""Strict JSON container. For type checkers: `JSONArray[T] | JSONObject[T]`."""

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
    type JSONValue = Annotated[  # NOTE: document somewhere that you can't do isinstance because these are type aliases
        JSONScalar | JSONContainer[JSONValue],
        Field(),
    ]
else:

    class JSONValue:
        """
        Strict, recursively validated JSON value; no implicit coercions.

        For type checkers: `JSONBoolean | JSONNumber | JSONString | JSONNull | JSONArray[JSONValue] | JSONObject[JSONValue]`.

        Notes:
            - Containers are restricted to `list` and `dict[str, ...]`.
            - Numbers are restricted to `int` or finite `float` (no `NaN` or `Infinity`).
            - Use `JSONBound` as a TypeVar bound when you need a static type constraint without
              Pydantic enforcement; use `JSONValue` when you need strict runtime validation.
            - Due to `list` invariance, narrower types such as `JSONArray[JSONNumber]` are not
              statically assignable to `JSONValue`. Use `cast(JSONValue, value)` at the return
              site; `validate_return=True` on `OperationSchema` enforces correctness at runtime.
              See [Limitations in Python's Type System](../developer-reference/limitations-in-python-type-system.md).
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
    return _cached_adapter(JSONValue).validate_python(obj, strict=True)


def _validate_typeform(unverified: object, exc_type: type[Exception]) -> TypeForm[Any]:
    """Validate a TypeForm parameter."""  # NOTE: move to JSONPointer if it's gonna raise InvalidJSONPointer
    try:
        _cached_adapter(unverified)  # type: ignore[arg-type]
    except Exception as e:
        raise exc_type(f"type parameter {unverified!r} must be a valid TypeForm") from e
    return cast(TypeForm[Any], unverified)


type JSONBound = JSONScalar | Sequence[JSONBound] | Mapping[str, JSONBound]
"""
TypeVar bound for JSON-shaped values, used by `JSONPointer[T]` and `JSONSelector[T]`.

For type checkers: `JSONScalar | Sequence[JSONBound] | Mapping[str, JSONBound]`.

Notes:
    This bound is intentionally permissive due to Python typing limitations. It accepts any
    `Sequence` (including `tuple`) and any `Mapping` (including custom mappings), rather than
    just `list` and `dict[str, ...]` as strict JSON requires. There is no way to express the
    exact recursive JSON container constraint in a TypeVar bound; see
    [Limitations in Python's Type System](../developer-reference/limitations-in-python-type-system.md).

    `JSONBound` is a static-only constraint with no runtime validation; it exists to let type
    checkers verify that a type parameter is plausibly JSON-shaped. Use `JSONValue` when you
    need strict Pydantic enforcement at runtime.
"""
