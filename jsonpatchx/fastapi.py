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
from typing import Any, TypeVar

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.params import Body as BodyParam
from fastapi.params import Depends as DependsParam
from fastapi.responses import JSONResponse
from pydantic import BaseModel, GetCoreSchemaHandler, GetJsonSchemaHandler
from pydantic_core import core_schema

from jsonpatchx.exceptions import (
    PatchConflictError,
    PatchError,
    PatchInputError,
    PatchInternalError,
)
from jsonpatchx.pydantic import JsonPatchFor

JSON_PATCH_MEDIA_TYPE = "application/json-patch+json"
PatchT = TypeVar("PatchT", bound=BaseModel)


class PatchFailureDetailResponse(BaseModel):
    index: int
    op: dict[str, Any]
    message: str
    cause_type: str | None = None


class PatchErrorResponse(BaseModel):
    detail: str | PatchFailureDetailResponse


# Internal schema helpers


def _patch_body_annotation(patch_model: type[Any]) -> type[Any]:
    class PatchBodyAnnotation:
        __patch_model__ = patch_model
        __patch_core_schema__: core_schema.CoreSchema | None = None

        @classmethod
        def __get_pydantic_core_schema__(
            cls, source_type: Any, handler: GetCoreSchemaHandler
        ) -> core_schema.CoreSchema:
            original_schema = handler.generate_schema(cls.__patch_model__)
            cls.__patch_core_schema__ = original_schema
            metadata = {
                "pydantic_js_annotation_functions": [lambda _c, h: h(original_schema)]
            }
            return core_schema.any_schema(
                metadata=metadata,
                serialization=core_schema.wrap_serializer_function_ser_schema(
                    function=lambda v, h: h(v),
                    schema=original_schema,
                ),
            )

        @classmethod
        def __get_pydantic_json_schema__(
            cls, schema: core_schema.CoreSchema, handler: GetJsonSchemaHandler
        ) -> dict[str, Any]:
            core_schema_to_use = cls.__patch_core_schema__ or schema
            return handler(core_schema_to_use)

    PatchBodyAnnotation.__name__ = f"{patch_model.__name__}Body"
    return PatchBodyAnnotation


# Error helpers


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
    """Register a single FastAPI exception handler for PatchError.

    Example:

        app = FastAPI()
        install_jsonpatch_error_handlers(app)
    """

    @app.exception_handler(PatchError)
    def _patch_error_handler(request: Request, exc: PatchError) -> JSONResponse:
        return _patch_error_response_map(exc)


def patch_error_openapi_responses() -> dict[int | str, dict[str, Any]]:
    """Return OpenAPI response schema entries for JSON Patch errors.

    Example:

        @app.patch("/items/{item_id}", responses=patch_error_openapi_responses())
        def patch_item(...):
            ...
    """
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


# Content type helpers


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
    """Return a dependency list that enforces the JSON Patch media type.

    Example:

        @app.patch("/items/{item_id}", dependencies=patch_content_type_dependency(True))
        def patch_item(...):
            ...
    """
    if not enabled:
        return []

    def _dep(request: Request) -> None:
        _enforce_json_patch_content_type(request, media_type=media_type)

    return [Depends(_dep)]


# OpenAPI helpers


def patch_request_body(
    patch_model: type[JsonPatchFor[Any, Any]],
    examples: dict[str, Any] | None = None,
    *,
    allow_application_json: bool = False,
    media_type: str = JSON_PATCH_MEDIA_TYPE,
    request_body_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenAPI requestBody for JSON Patch with optional examples.

    Convention: JSON Patch requests should use ``application/json-patch+json``.
    This opinionated library advertises only that media type by default.
    Set ``allow_application_json=True`` to also document ``application/json`` for
    compatibility when you choose to accept it.

    Example:

        @app.patch(
            "/configs/{config_id}",
            openapi_extra=patch_request_body(ConfigPatch, examples={"set": {...}}),
        )
        def patch_config(...):
            ...
    """
    schema_ref = f"#/components/schemas/{patch_model.__name__}"
    content: dict[str, Any] = {
        media_type: {"schema": {"$ref": schema_ref}},
    }
    if examples:
        content[media_type]["examples"] = examples
    if allow_application_json:
        content["application/json"] = {"schema": {"$ref": schema_ref}}
    request_body: dict[str, Any] = {"required": True, "content": content}
    if request_body_overrides:
        override_content = request_body_overrides.get("content")
        if isinstance(override_content, dict):
            content.update(override_content)
        request_body.update(
            {
                key: value
                for key, value in request_body_overrides.items()
                if key != "content"
            }
        )
    return {"requestBody": request_body}


def patch_route_kwargs(
    patch_model: type[JsonPatchFor[Any, Any]] | None = None,
    examples: dict[str, Any] | None = None,
    *,
    allow_application_json: bool = False,
    media_type: str = JSON_PATCH_MEDIA_TYPE,
    request_body_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return FastAPI decorator kwargs that keep docs and enforcement aligned.

    This opinionated helper adds:
    - ``responses`` for JSON Patch errors
    - ``dependencies`` that enforce JSON Patch media type by default
    - ``openapi_extra`` for the request body when ``patch_model`` is provided

    If ``allow_application_json`` is True, ``application/json`` is documented
    and enforcement is disabled to allow both.
    """
    kwargs: dict[str, Any] = {
        "responses": patch_error_openapi_responses(),
        "dependencies": patch_content_type_dependency(
            not allow_application_json,
            media_type=media_type,
        ),
    }
    if patch_model is not None:
        kwargs["openapi_extra"] = patch_request_body(
            patch_model,
            examples,
            allow_application_json=allow_application_json,
            media_type=media_type,
            request_body_overrides=request_body_overrides,
        )
    return kwargs


# Dependency helpers


def PatchDependency(
    patch_model: type[PatchT],
    *,
    request_param: BodyParam,
    error_mapper: Callable[[PatchInputError, Any], Exception] | None = None,
) -> Callable[[Any], PatchT]:
    """Return a dependency function that validates a JSON Patch document.

    Example:
        from typing import Annotated

        PatchBody = JsonPatchFor[User, UserRegistry]
        PatchDepends = PatchDependency(
            PatchBody,
            request_param=Body(..., media_type=JSON_PATCH_MEDIA_TYPE),
        )

        @app.patch("/users/{user_id}")
        def patch_user(
            user_id: int,
            patch: Annotated[PatchBody, Depends(PatchDepends)],
        ) -> User:
            return patch.apply(load_user(user_id))
    """

    def _dep(patch: Any = request_param) -> PatchT:
        try:
            if isinstance(patch, patch_model):
                patch_payload = patch.model_dump(mode="json", by_alias=True)
                return patch_model.model_validate(patch_payload)
            return patch_model.model_validate(patch)
        except PatchInputError as e:
            if error_mapper:
                raise error_mapper(e, patch) from e
            raise RequestValidationError(
                [
                    {
                        "loc": ("body",),
                        "msg": str(e),
                        "type": "value_error.patch_input",
                        "ctx": {"cause_type": type(e).__name__},
                    }
                ],
                body=patch,
            ) from e

    _dep.__annotations__["patch"] = _patch_body_annotation(patch_model)
    _dep.__annotations__["return"] = patch_model

    return _dep
