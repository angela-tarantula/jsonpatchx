"""
FastAPI integration helpers for jsonpatch.

Default error mapping:
- 415: Wrong Content-Type for JSON Patch (application/json-patch+json)
- 400: Malformed JSON (cannot parse request body)
- 422: Patch input validation errors (invalid pointers, invalid operations, model revalidation)
- 409: Patch is valid but cannot be applied to current resource state
- 500: Server misconfiguration or unexpected failures (e.g., invalid registry/op classes)

If your API treats "missing path / invalid index" as a client semantic error rather than
a state conflict, map PatchConflictError to 422 instead.
"""

from __future__ import annotations

from collections.abc import Callable
from inspect import isclass
from typing import Any, Protocol, Self, TypeVar

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.params import Depends as DependsParam
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from jsonpatchx.exceptions import (
    PatchConflictError,
    PatchError,
    PatchInputError,
    PatchInternalError,
)
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.registry import AnyRegistry, GenericOperationRegistry

JSON_PATCH_MEDIA_TYPE = "application/json-patch+json"
ModelT = TypeVar("ModelT", bound=BaseModel)


class _PatchModel(Protocol):
    @classmethod
    def model_validate(cls, obj: Any) -> Self: ...


PatchT = TypeVar("PatchT", bound=_PatchModel)

# FastAPI helpers


def _require_registry_type(registry: object) -> type[AnyRegistry]:
    if not isclass(registry) or not issubclass(registry, GenericOperationRegistry):
        raise TypeError(
            "registry must be an OperationRegistry type (OperationRegistry[...]), "
            f"got {registry!r}"
        )
    return registry


class PatchFailureDetailResponse(BaseModel):
    index: int
    op: dict[str, Any]
    message: str
    cause_type: str | None = None


class PatchErrorResponse(BaseModel):
    detail: str | PatchFailureDetailResponse


def _patch_error_response_map(exc: PatchError) -> JSONResponse:
    """Map a PatchError to a JSONResponse for FastAPI exception handlers."""
    if isinstance(exc, PatchInternalError):
        detail = exc.detail
        payload = PatchFailureDetailResponse(
            index=detail.index,
            op=detail.op.model_dump(mode="json", by_alias=True),
            message=detail.message,
            cause_type=detail.cause_type,
        )
        return JSONResponse(
            status_code=500, content=PatchErrorResponse(detail=payload).model_dump()
        )

    if isinstance(exc, PatchInputError):
        return JSONResponse(
            status_code=422, content=PatchErrorResponse(detail=str(exc)).model_dump()
        )

    if isinstance(exc, PatchConflictError):
        return JSONResponse(
            status_code=409, content=PatchErrorResponse(detail=str(exc)).model_dump()
        )

    return JSONResponse(
        status_code=500, content=PatchErrorResponse(detail=str(exc)).model_dump()
    )


def install_jsonpatch_error_handlers(app: FastAPI) -> None:
    """Register a single FastAPI exception handler for PatchError."""

    @app.exception_handler(PatchError)
    def _patch_error_handler(request: Request, exc: PatchError) -> JSONResponse:
        return _patch_error_response_map(exc)


def patch_error_openapi_responses() -> dict[int | str, dict[str, Any]]:
    """Return OpenAPI response schema entries for JSON Patch errors."""
    schema = {
        "type": "object",
        "properties": {
            "detail": {
                "oneOf": [
                    {"type": "string"},
                    {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "op": {"type": "object"},
                            "message": {"type": "string"},
                            "cause_type": {"type": ["string", "null"]},
                        },
                        "required": ["index", "op", "message"],
                    },
                ]
            }
        },
        "required": ["detail"],
    }
    return {
        400: {
            "description": "Malformed JSON",
            "content": {"application/json": {"schema": schema}},
        },
        409: {
            "description": "Patch cannot be applied to current resource state",
            "content": {"application/json": {"schema": schema}},
        },
        422: {
            "description": "Patch document validation error",
            "content": {"application/json": {"schema": schema}},
        },
        415: {
            "description": "Unsupported Media Type",
            "content": {"application/json": {"schema": schema}},
        },
        500: {
            "description": "Patch execution error",
            "content": {"application/json": {"schema": schema}},
        },
    }


def _enforce_json_patch_content_type(
    request: Request, *, media_type: str = JSON_PATCH_MEDIA_TYPE
) -> None:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith(media_type):
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported Media Type. Use {media_type} for JSON Patch requests."
            ),
        )


def patch_content_type_dependency(
    enabled: bool, *, media_type: str = JSON_PATCH_MEDIA_TYPE
) -> list[DependsParam]:
    """Return a dependency list that enforces the JSON Patch media type."""
    if not enabled:
        return []

    def _dep(request: Request) -> None:
        _enforce_json_patch_content_type(request, media_type=media_type)

    return [Depends(_dep)]


def patch_request_body(
    patch_model: type[JsonPatchFor[Any, Any]],
    examples: dict[str, Any] | None = None,
    *,
    include_application_json: bool = True,
    media_type: str = JSON_PATCH_MEDIA_TYPE,
) -> dict[str, Any]:
    """Build an OpenAPI requestBody for JSON Patch with optional examples."""
    schema_ref = f"#/components/schemas/{patch_model.__name__}"
    content: dict[str, Any] = {
        media_type: {"schema": {"$ref": schema_ref}},
    }
    if examples:
        content[media_type]["examples"] = examples
    if include_application_json:
        content["application/json"] = {"schema": {"$ref": schema_ref}}
    return {"requestBody": {"required": True, "content": content}}


def PatchDependency(
    patch_model: type[PatchT],
    *,
    app: FastAPI | None = None,
    body_param: Any | None = None,
) -> Callable[[Any], PatchT]:
    """
    Return a dependency function that validates a JSON Patch document with FastAPI-style errors.
    """
    if app is not None:
        register_patch_schema(app, patch_model)

    def _dep(patch: Any = body_param) -> PatchT:
        try:
            return patch_model.model_validate(patch)
        except PatchInputError as e:
            raise RequestValidationError(
                [{"loc": ("body",), "msg": str(e), "type": "value_error.patch_input"}],
                body=patch,
            ) from e

    return _dep


def _register_patch_schema_in_openapi(
    schema: dict[str, Any],
    patch_model: type[Any],
) -> None:
    schemas = schema.setdefault("components", {}).setdefault("schemas", {})
    if patch_model.__name__ in schemas:
        return

    patch_schema = patch_model.model_json_schema(
        ref_template="#/components/schemas/{model}"
    )
    defs = patch_schema.pop("$defs", {})
    for key, value in defs.items():
        schemas.setdefault(key, value)
    schemas[patch_model.__name__] = patch_schema


def register_patch_schema(app: FastAPI, patch_model: type[Any]) -> None:
    """
    Register a patch model's schema in OpenAPI components so $ref works in docs.
    """
    if app.openapi_schema is not None:
        _register_patch_schema_in_openapi(app.openapi_schema, patch_model)
        return

    pending = getattr(app.state, "_jsonpatchx_patch_models", None)
    if pending is None:
        pending = set()
        app.state._jsonpatchx_patch_models = pending
    pending.add(patch_model)

    if getattr(app.state, "_jsonpatchx_openapi_wrapped", False):
        return

    original_openapi = app.openapi

    def wrapped_openapi() -> dict[str, Any]:
        schema = original_openapi()
        for model in app.state._jsonpatchx_patch_models:
            _register_patch_schema_in_openapi(schema, model)
        return schema

    app.state._jsonpatchx_openapi_wrapped = True
    app.openapi = wrapped_openapi  # type: ignore[method-assign]
