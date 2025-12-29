"""
FastAPI baseline — typical JSON Patch request schema (loose typing),
but still applies patches via THIS project's engine for a fair comparison.

Run
  uvicorn examples.openapi_baseline:app --reload
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import Body, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from jsonpatch import JsonPatch  # any JsonPatch library works
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
UserPatch = list[PatchOp]


_USERS: dict[int, User] = {
    1: User(id=1, name="Angela", tags=["admin"]),
    2: User(id=2, name="Pat", tags=["editor", "qa"]),
}


@app.get("/users/{user_id}", response_model=User, tags=["users"])
def get_user(user_id: int) -> User:
    user = _USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.patch(
    "/users/{user_id}",
    response_model=User,
    tags=["users"],
    summary="Patch a user (baseline)",
    description=(
        "Baseline request shape: a list of ops with `path: str` and `value: Any`.\n\n"
        "For a fair comparison, this endpoint still applies patches using this project's engine, "
        "but it lacks the library's richer OpenAPI schema."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                JSON_PATCH_MEDIA_TYPE: {
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
                    }
                },
                "application/json": {},
            },
        }
    },
)
def patch_user(
    user_id: int,
    patch: UserPatch = Body(
        ...,
        media_type=JSON_PATCH_MEDIA_TYPE,
        description=(
            "Baseline patch body. Prefer Content-Type: application/json-patch+json."
        ),
    ),
) -> User:
    user = _USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    raw_ops: list[dict[str, JSONValue]] = [
        op.model_dump(by_alias=True)
        for op in patch  # type: ignore[assignment]
    ]

    updated = JsonPatch(raw_ops).apply(user)
    _USERS[user_id] = updated
    return updated


@app.get("/health", tags=["meta"])
def health(response: Response) -> dict[str, Any]:
    response.headers["cache-control"] = "no-store"
    return {"status": "ok"}
