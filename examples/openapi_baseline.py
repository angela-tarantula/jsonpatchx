"""
FastAPI baseline — typical JSON Patch request schema (loose typing),
but still applies patches via THIS project's engine for a fair comparison.

Run
  uvicorn examples.openapi_baseline:app --reload
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Path, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, RootModel, ValidationError
from jsonpatch import JsonPatch  # any JsonPatch library works
from jsonpatch.exceptions import PatchError
from jsonpatch.types import JSONValue

JSON_PATCH_MEDIA_TYPE = "application/json-patch+json"

app = FastAPI(
    title="Baseline PATCH demo (standard JSON Patch shape)",
    version="0.1.0",
    description=(
        "Baseline comparison: request bodies look like conventional JSON Patch models "
        "(loose typing). Patches are applied using this project's engine."
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


# Baseline operation models: permissive and conventional.


class AddOp(BaseModel):
    op: Literal["add"] = "add"
    path: str
    value: Any


class RemoveOp(BaseModel):
    op: Literal["remove"] = "remove"
    path: str


class ReplaceOp(BaseModel):
    op: Literal["replace"] = "replace"
    path: str
    value: Any


class MoveOp(BaseModel):
    op: Literal["move"] = "move"
    from_: str = Field(alias="from")
    path: str


class CopyOp(BaseModel):
    op: Literal["copy"] = "copy"
    from_: str = Field(alias="from")
    path: str


class TestOp(BaseModel):
    op: Literal["test"] = "test"
    path: str
    value: Any


PatchOp = AddOp | RemoveOp | ReplaceOp | MoveOp | CopyOp | TestOp


class UserPatch(RootModel[list[PatchOp]]):
    pass


class JsonPatchBody(RootModel[list[PatchOp]]):
    pass


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
        media_type=JSON_PATCH_MEDIA_TYPE,
        description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
    ),
) -> User:
    user = _USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    raw_ops: list[dict[str, JSONValue]] = [
        op.model_dump(by_alias=True) for op in patch.root
    ]

    updated = JsonPatch(raw_ops).apply(user)
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
    patch: JsonPatchBody = Body(
        ...,
        description="JSON Patch document. Prefer Content-Type: application/json-patch+json.",
        media_type=JSON_PATCH_MEDIA_TYPE,
    ),
) -> JSONValue:
    doc = _CONFIGS.get(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")

    raw_ops: list[dict[str, JSONValue]] = [
        op.model_dump(by_alias=True) for op in patch.root
    ]

    updated = JsonPatch(raw_ops).apply(doc)
    _CONFIGS[config_id] = updated
    return updated


@app.get("/health", tags=["meta"])
def health(response: Response) -> dict[str, Any]:
    response.headers["cache-control"] = "no-store"
    return {"status": "ok"}
