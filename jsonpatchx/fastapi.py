from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.params import Body as BodyParam
from fastapi.params import Depends as DependsParam
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from jsonpatchx.exceptions import (
    InvalidPatchResult,
    InvalidPatchTarget,
    PatchConflictError,
    PatchError,
    PatchInternalError,
)
from jsonpatchx.pydantic import JsonPatchFor

JSON_PATCH_MEDIA_TYPE = "application/json-patch+json"


class PatchErrorResponse(BaseModel):
    type: str
    detail: str
    index: int | None = None
    operation: dict[str, Any] | None = None
    errors: list[dict[str, Any]] | None = None


# Public helpers


def install_jsonpatch_error_handlers(app: FastAPI) -> None:
    """Register FastAPI exception handlers for `PatchError` and `InvalidPatchTarget`.

    Arguments:
        app: The FastAPI application to configure.

    Notes:
        Default error mapping:

        | Status | Cause |
        |--------|-------|
        | 415 | Wrong Content-Type for JSON Patch (`application/json-patch+json`); response includes an `Accept-Patch` header naming the expected media type |
        | 422 | Request validation errors (malformed JSON, invalid operations or pointers, model revalidation failure) |
        | 409 | Patch is valid but cannot be applied to current resource state |
        | 500 | Unexpected execution failures (`PatchInternalError`) or a bad patch target (`InvalidPatchTarget`) |

    Examples:

        app = FastAPI()
        install_jsonpatch_error_handlers(app)
    """

    @app.exception_handler(PatchError)
    def _patch_error_handler(request: Request, exc: PatchError) -> JSONResponse:
        return _patch_error_response_map(exc)

    @app.exception_handler(InvalidPatchTarget)
    def _invalid_patch_target_handler(
        request: Request, exc: InvalidPatchTarget
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=PatchErrorResponse(
                type=InvalidPatchTarget.error_type, detail=str(exc)
            ).model_dump(),
        )


def patch_error_openapi_responses() -> dict[int | str, dict[str, Any]]:
    """Return OpenAPI response schema entries for JSON Patch errors.

    Returns:
        A `responses` mapping suitable for FastAPI route decorators or
        `openapi_extra`.

    Examples:

        @app.patch("/items/{item_id}", responses=patch_error_openapi_responses())
        def patch_item(...):
            ...
    """
    patch_error_schema = PatchErrorResponse.model_json_schema()
    validation_schema = {"$ref": "#/components/schemas/HTTPValidationError"}
    validation_or_patch_schema = {
        "oneOf": [
            patch_error_schema,
            validation_schema,
        ]
    }
    return {
        409: {
            "description": "Patch cannot be applied to current resource state",
            "content": {"application/json": {"schema": patch_error_schema}},
        },
        422: {
            "description": "Request validation or patch document validation error",
            "content": {"application/json": {"schema": validation_or_patch_schema}},
        },
        415: {
            "description": "Unsupported Media Type",
            "content": {"application/json": {"schema": patch_error_schema}},
        },
        500: {
            "description": "Patch execution error",
            "content": {"application/json": {"schema": patch_error_schema}},
        },
    }


def patch_content_type_dependency(
    enabled: bool, *, media_type: str = JSON_PATCH_MEDIA_TYPE
) -> list[DependsParam]:
    """Return a dependency list that enforces the JSON Patch media type.

    Arguments:
        enabled: Whether content-type enforcement should be enabled.
        media_type: The accepted JSON Patch media type.

    Returns:
        A dependency list suitable for FastAPI route decorators.

    Examples:

        @app.patch("/items/{item_id}", dependencies=patch_content_type_dependency(True))
        def patch_item(...):
            ...
    """
    if not enabled:
        return []

    def _dep(request: Request) -> None:
        _enforce_json_patch_content_type(request, media_type=media_type)

    return [Depends(_dep)]


def patch_request_body(
    patch_model: type[JsonPatchFor[Any, Any]],
    examples: dict[str, Any] | None = None,
    *,
    allow_application_json: bool = False,
    media_type: str = JSON_PATCH_MEDIA_TYPE,
    request_body_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an OpenAPI requestBody for JSON Patch with optional examples.

    Arguments:
        patch_model: The generated `JsonPatchFor[...]` model exposed in OpenAPI.
        examples: Optional OpenAPI examples keyed by example name.
        allow_application_json: Whether `application/json` should also be
            documented alongside the JSON Patch media type.
        media_type: The primary JSON Patch media type to document.
        request_body_overrides: Optional shallow overrides for the generated
            top-level `requestBody` object. A provided `content` map is merged
            into the generated content entries.

    Returns:
        An `openapi_extra` fragment containing a `requestBody` entry.

    Notes:
        JSON Patch requests should use `application/json-patch+json`. This
        library advertises only that media type by default. Set
        `allow_application_json=True` to also document `application/json` when
        you intentionally accept both.

    Examples:

        @app.patch(
            "/configs/{config_id}",
            openapi_extra=patch_request_body(ConfigPatch, examples={"set": {...}}),
        )
        def patch_config(...):
            ...

        # Add an extra media type and override requestBody.required
        openapi_extra=patch_request_body(
            ConfigPatch,
            request_body_overrides={
                "required": False,
                "content": {"application/merge-patch+json": {"schema": {"type": "object"}}},
            },
        )
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

    Arguments:
        patch_model: Optional patch model used to generate request-body docs.
        examples: Optional OpenAPI examples for the patch request body.
        allow_application_json: Whether `application/json` should be documented
            and accepted alongside the JSON Patch media type.
        media_type: The primary JSON Patch media type to document.
        request_body_overrides: Optional shallow overrides for the generated
            `requestBody`.

    Returns:
        A FastAPI route kwargs mapping containing `responses`,
        `dependencies`, and optionally `openapi_extra`.

    Notes:
        If `allow_application_json` is true, `application/json` is documented
        and content-type enforcement is disabled to allow both media types.
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


@dataclass(frozen=True)
class JsonPatchRoute:
    """Configure JSON Patch routes with a single source of truth."""

    patch_model: type[JsonPatchFor[Any, Any]]
    examples: dict[str, Any] | None = None
    strict_content_type: bool = True
    media_type: str = JSON_PATCH_MEDIA_TYPE
    request_body_overrides: dict[str, Any] | None = None
    request_param_overrides: dict[str, Any] | None = None

    def route_kwargs(self) -> dict[str, Any]:
        """Return FastAPI route kwargs for this JSON Patch contract."""
        return patch_route_kwargs(
            self.patch_model,
            examples=self.examples,
            allow_application_json=not self.strict_content_type,
            media_type=self.media_type,
            request_body_overrides=self.request_body_overrides,
        )

    def Body(self) -> BodyParam:
        """Return the configured FastAPI `Body(...)` parameter."""
        body_kwargs = dict(self.request_param_overrides or {})
        if self.strict_content_type:
            body_kwargs.setdefault("media_type", self.media_type)
        return cast(BodyParam, Body(..., **body_kwargs))


def _patch_error_response_map(exc: PatchError) -> JSONResponse:
    """Map a PatchError to a JSONResponse for FastAPI exception handlers.

    Expected mappings:
        - InvalidPatchResult -> 422 (patched result fails the target model
          schema; a content/schema problem, not a resource-state conflict)
        - PatchConflictError, TestOpFailed -> 409
        - PatchInternalError, unrecognized PatchError -> 500

    TODO: Integration tests in tests/integration/fastapi/runtime/ should cover
          each failure path and assert both the HTTP status code and the
          exception that triggered it, ideally with match="..." on the error
          message. Once user-facing error messages are stabilized, assert their
          content too.
    """
    operation_payload = (
        exc.operation.model_dump(mode="json", by_alias=True)
        if exc.operation is not None
        else None
    )

    if isinstance(exc, PatchInternalError):
        return JSONResponse(
            status_code=500,
            content=PatchErrorResponse(
                type=exc.error_type,
                detail=str(exc),
                index=exc.index,
                operation=operation_payload,
            ).model_dump(),
        )

    if isinstance(exc, InvalidPatchResult):
        return JSONResponse(
            status_code=422,
            content=PatchErrorResponse(
                type=exc.error_type,
                detail=str(exc),
                index=exc.index,
                operation=operation_payload,
                errors=exc.errors,
            ).model_dump(),
        )

    if isinstance(exc, PatchConflictError):
        return JSONResponse(
            status_code=409,
            content=PatchErrorResponse(
                type=exc.error_type,
                detail=str(exc),
                index=exc.index,
                operation=operation_payload,
            ).model_dump(),
        )

    return JSONResponse(
        status_code=500,
        content=PatchErrorResponse(
            type=exc.error_type,
            detail=str(exc),
            index=exc.index,
            operation=operation_payload,
        ).model_dump(),
    )


def _enforce_json_patch_content_type(
    request: Request, *, media_type: str = JSON_PATCH_MEDIA_TYPE
) -> None:
    content_type = request.headers.get("content-type", "")
    if not content_type.lower().startswith(media_type.lower()):
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported Media Type. Use {media_type} for JSON Patch requests."
            ),
            headers={"Accept-Patch": media_type},
        )
