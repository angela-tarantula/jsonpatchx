from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, cast

from pydantic import Field, TypeAdapter
from typing_extensions import TypeForm, TypeIs

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

# type-narrowing helpers
# NOTE: consider making public type-narrowing helpers


def _is_container(value: object) -> TypeIs[JSONContainer[JSONValue]]:
    """Internal: runtime check for JSON containers (dict/list)."""
    return isinstance(value, (list, dict))


def _is_object(value: object) -> TypeIs[JSONObject[JSONValue]]:
    return isinstance(value, dict)


def _is_array(value: object) -> TypeIs[JSONArray[JSONValue]]:
    return isinstance(value, list)


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


def _validate_JSONValue(obj: object) -> JSONValue:
    return _type_adapter_for(JSONValue).validate_python(obj, strict=True)


def _validate_typeform(unverified: object) -> TypeForm[Any]:
    """Validate a TypeForm parameter."""
    try:
        _type_adapter_for(unverified)  # type: ignore[arg-type]
    except Exception as e:
        raise InvalidJSONPointer(
            f"JSONPointer type parameter {unverified!r} must be a valid TypeForm"
        ) from e
    return cast(TypeForm[Any], unverified)
