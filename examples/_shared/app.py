from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError

from jsonpatch.exceptions import PatchError

from .media import JSON_PATCH_MEDIA_TYPE
from .responses import patch_error_response


def create_app(*, title: str, description: str, version: str = "0.1.0") -> FastAPI:
    app = FastAPI(title=title, description=description, version=version)
    install_error_handlers(app)

    @app.get("/", include_in_schema=False)
    def _root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(PatchError)
    def _patch_error_handler(request: Request, exc: PatchError) -> JSONResponse:
        return patch_error_response(exc)

    @app.exception_handler(ValidationError)
    def _validation_error_handler(
        request: Request, exc: ValidationError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": exc.errors()})


def enforce_json_patch_content_type(request: Request) -> None:
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith(JSON_PATCH_MEDIA_TYPE):
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported Media Type. Use application/json-patch+json for JSON Patch requests."
            ),
        )


def patch_request_body(
    schema_ref: str,
    examples: dict[str, Any] | None = None,
    *,
    include_application_json: bool = True,
) -> dict[str, Any]:
    content: dict[str, Any] = {
        JSON_PATCH_MEDIA_TYPE: {"schema": {"$ref": schema_ref}},
    }
    if examples:
        content[JSON_PATCH_MEDIA_TYPE]["examples"] = examples
    if include_application_json:
        content["application/json"] = {"schema": {"$ref": schema_ref}}
    return {"requestBody": {"required": True, "content": content}}


def patch_content_type_dependency(enabled: bool) -> list[Callable[..., Any]]:
    if not enabled:
        return []
    return [Depends(enforce_json_patch_content_type)]
