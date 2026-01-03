"""
FastAPI integration helpers for jsonpatch.

Default error mapping:
- 415: Wrong Content-Type for JSON Patch (application/json-patch+json)
- 400: Malformed JSON (cannot parse request body)
- 422: Patch document validation errors (Pydantic validation, invalid pointer strings)
- 409: Patch is valid but cannot be applied to current resource state
- 500: Server misconfiguration or unexpected failures (e.g., invalid registry/op classes)

If your API treats "missing path / invalid index" as a client semantic error rather than
a state conflict, map PatchApplicationError to 422 instead.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from jsonpatch.exceptions import (
    InvalidJsonPatch,
    InvalidJSONPointer,
    PatchApplicationError,
    PatchError,
    PatchExecutionError,
)
from jsonpatch.pydantic import _BasePatchBody, make_json_patch_body
from jsonpatch.registry import OperationRegistry

JSON_PATCH_MEDIA_TYPE = "application/json-patch+json"

# FastAPI helpers


class PatchFailureDetailResponse(BaseModel):
    index: int
    op: dict[str, Any]
    message: str
    cause_type: str | None = None


class PatchErrorResponse(BaseModel):
    detail: str | PatchFailureDetailResponse


def patch_error_response(exc: PatchError) -> JSONResponse:
    if isinstance(exc, PatchExecutionError):
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

    if isinstance(exc, PatchApplicationError):
        return JSONResponse(
            status_code=409, content=PatchErrorResponse(detail=str(exc)).model_dump()
        )

    if isinstance(exc, (InvalidJsonPatch, InvalidJSONPointer)):
        return JSONResponse(
            status_code=422, content=PatchErrorResponse(detail=str(exc)).model_dump()
        )

    return JSONResponse(
        status_code=500, content=PatchErrorResponse(detail=str(exc)).model_dump()
    )


def patch_error_responses() -> dict[int, dict[str, Any]]:
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


def install_jsonpatch_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PatchError)
    def _patch_error_handler(request: Request, exc: PatchError) -> JSONResponse:
        return patch_error_response(exc)


def _enforce_json_patch_content_type(
    request: Request, *, media_type: str = JSON_PATCH_MEDIA_TYPE
) -> None:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith(media_type):
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported Media Type. Use application/json-patch+json for JSON Patch requests."
            ),
        )


def patch_content_type_dependency(
    enabled: bool, *, media_type: str = JSON_PATCH_MEDIA_TYPE
) -> list[Callable[..., Any]]:
    if not enabled:
        return []

    def _dep(request: Request) -> None:
        _enforce_json_patch_content_type(request, media_type=media_type)

    return [Depends(_dep)]


def patch_request_body(
    schema_ref: str,
    examples: dict[str, Any] | None = None,
    *,
    include_application_json: bool = True,
    media_type: str = JSON_PATCH_MEDIA_TYPE,
) -> dict[str, Any]:
    content: dict[str, Any] = {
        media_type: {"schema": {"$ref": schema_ref}},
    }
    if examples:
        content[media_type]["examples"] = examples
    if include_application_json:
        content["application/json"] = {"schema": {"$ref": schema_ref}}
    return {"requestBody": {"required": True, "content": content}}


# https://github.com/fastapi/fastapi/discussions/10864
# Due to a limitation of FastAPI, need make_json_patch_body_with_dep instead of make_json_patch_body


def make_json_patch_body_with_dep(
    registry: OperationRegistry | None = None,
    *,
    name: str = "JsonPatchBody",
    media_type: str | None = JSON_PATCH_MEDIA_TYPE,
    include_application_json: bool = True,
    examples: dict[str, Any] | None = None,
    body_kwargs: dict[str, Any] | None = None,
    app: FastAPI | None = None,
) -> tuple[
    type[_BasePatchBody],
    Callable[..., _BasePatchBody],
    dict[str, Any] | None,
]:
    """
    Create a JSON Patch RootModel plus a FastAPI dependency that injects registry context.

    Returns (PatchBody, dependency, openapi_extra).
    """
    registry = registry or OperationRegistry.standard()
    PatchBody = make_json_patch_body(registry, name=name)
    if app is not None:
        _register_patch_schema(app, PatchBody)

    body_kwargs = body_kwargs or {}
    if media_type is not None:
        body_param = Body(..., media_type=media_type, **body_kwargs)
    else:
        body_param = Body(..., **body_kwargs)

    def _dep(patch: Any = body_param) -> _BasePatchBody:
        try:
            return PatchBody.model_validate(patch, context=registry._ctx)
        except ValidationError as e:
            raise RequestValidationError(e.errors(), body=patch) from e
        except InvalidJSONPointer as e:
            raise RequestValidationError(
                [{"loc": ("body",), "msg": str(e), "type": "value_error.jsonpointer"}],
                body=patch,
            ) from e

    openapi_extra = None
    if media_type is not None:
        schema_ref = f"#/components/schemas/{PatchBody.__name__}"
        content: dict[str, Any] = {media_type: {"schema": {"$ref": schema_ref}}}
        if examples:
            content[media_type]["examples"] = examples
        if include_application_json:
            content["application/json"] = {"schema": {"$ref": schema_ref}}
        openapi_extra = {"requestBody": {"required": True, "content": content}}

    return PatchBody, _dep, openapi_extra


def _register_patch_schema(app: FastAPI, patch_model: type[_BasePatchBody]) -> None:
    """
    Register a patch model's schema in OpenAPI components so $ref works in docs.
    """
    original_openapi = app.openapi

    def _register(schema: dict[str, Any]) -> None:
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

    # Wrap existing OpenAPI behavior
    def wrapped_openapi() -> dict[str, Any]:
        schema = original_openapi()
        _register(schema)
        return schema

    cast(Any, app).openapi = wrapped_openapi
