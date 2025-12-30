"""
FastAPI + jsonpatch (this library) — OpenAPI demo (standard RFC 6902 ops).

What this file demonstrates
- Model-aware patching via JsonPatchFor[User]
- Typed ops applied to untyped JSONValue documents via make_json_patch_body(...)
- Strong OpenAPI: discriminator on "op", JSON Pointer format, JSONValue schema, named examples
- Documents Content-Type: application/json-patch+json (does NOT enforce it)

Run
  uvicorn examples.openapi_demo:app --reload
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Path, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError
from jsonpatch import JsonPatchFor, OperationRegistry, make_json_patch_body
from jsonpatch.exceptions import PatchError
from jsonpatch.types import JSONValue

JSON_PATCH_MEDIA_TYPE = "application/json-patch+json"

app = FastAPI(
    title="JsonPatch OpenAPI demo (this library)",
    version="0.1.0",
    description=(
        "Demonstrates RFC 6902 JSON Patch with typed operation schemas, typed JSON Pointers, "
        "and OpenAPI generation."
    ),
)


@app.exception_handler(PatchError)
def patch_error_handler(request: Request, exc: PatchError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


class User(BaseModel):
    id: int
    name: str
    tags: list[str] = Field(default_factory=list)


UserPatch = JsonPatchFor[User]
ConfigPatchBody = make_json_patch_body(OperationRegistry.standard())

_USERS: dict[int, User] = {
    1: User(id=1, name="Angela", tags=["admin"]),
    2: User(id=2, name="Pat", tags=["editor", "qa"]),
}

_CONFIGS: MutableMapping[str, JSONValue] = {
    "site": {"title": "Example", "features": {"chat": True}},
    "limits": {"max_users": 5, "trial": False},
}


@app.get(
    "/users/{user_id}",
    response_model=User,
    tags=["users"],
    summary="Get a user",
    description="Fetch a user by id.",
)
def get_user(
    user_id: int = Path(
        ...,
        description="Available users: 1, 2.",
        example=1,
    ),
) -> User:
    user = _USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.patch(
    "/users/{user_id}",
    response_model=User,
    tags=["users"],
    summary="Patch a user",
    description="Apply a JSON Patch document to a `User`.",
    responses={
        400: {
            "description": "Patch application error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                        "required": ["detail"],
                    }
                }
            },
        }
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                JSON_PATCH_MEDIA_TYPE: {
                    "schema": {"$ref": "#/components/schemas/UserPatch"},
                    "examples": {
                        "rename-user": {
                            "summary": "Rename a user",
                            "value": [
                                {"op": "replace", "path": "/name", "value": "Angela"}
                            ],
                        },
                        "append-tag": {
                            "summary": "Append a tag",
                            "value": [
                                {"op": "add", "path": "/tags/-", "value": "staff"}
                            ],
                        },
                    },
                },
                # Keep application/json as well, because FastAPI/Swagger often defaults to it anyway
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/UserPatch"}
                },
            },
        }
    },
)
def patch_user(
    user_id: int,
    patch: UserPatch = Body(
        ...,
        description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
        media_type=JSON_PATCH_MEDIA_TYPE,
    ),
) -> User:
    user = _USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    updated = patch.apply(user)
    _USERS[user_id] = updated
    return updated


@app.get(
    "/configs/{config_id}",
    response_model=Any,
    tags=["configs"],
    summary="Get a config",
    description="Fetch a config by id.",
)
def get_config(
    config_id: str = Path(
        ...,
        description="Available configs: site, limits.",
        example="site",
    ),
) -> JSONValue:
    doc = _CONFIGS.get(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    return doc


@app.patch(
    "/configs/{config_id}",
    response_model=Any,
    tags=["configs"],
    summary="Patch a config",
    description="Apply a JSON Patch document to a config (`JSONValue`).",
    responses={
        400: {
            "description": "Patch application error",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {"detail": {"type": "string"}},
                        "required": ["detail"],
                    }
                }
            },
        }
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                JSON_PATCH_MEDIA_TYPE: {
                    "schema": {"$ref": "#/components/schemas/JsonPatchBody"},
                    "examples": {
                        "enable-feature": {
                            "summary": "site: enable chat",
                            "value": [
                                {
                                    "op": "replace",
                                    "path": "/features/chat",
                                    "value": True,
                                }
                            ],
                        },
                        "bump-limit": {
                            "summary": "limits: bump max_users",
                            "value": [
                                {
                                    "op": "replace",
                                    "path": "/max_users",
                                    "value": 10,
                                }
                            ],
                        },
                    },
                },
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/JsonPatchBody"}
                },
            },
        }
    },
)
def patch_config(
    config_id: str,
    patch: ConfigPatchBody = Body(
        ...,
        description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
        media_type=JSON_PATCH_MEDIA_TYPE,
    ),
) -> JSONValue:
    doc = _CONFIGS.get(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    updated = patch.apply(doc)
    _CONFIGS[config_id] = updated
    return updated


@app.get("/health", tags=["meta"])
def health(response: Response) -> dict[str, Any]:
    response.headers["cache-control"] = "no-store"
    return {"status": "ok"}
