from collections.abc import MutableMapping
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from jsonpatch import JsonPatchFor, OperationRegistry, make_json_patch_body
from jsonpatch.types import JSONValue

app = FastAPI(title="jsonpatch FastAPI OpenAPI demo")


class User(BaseModel):
    id: int
    name: str
    tags: list[str] = Field(default_factory=list)


# Example 1: model-aware patches (JsonPatchFor)
UserPatch = JsonPatchFor[User]


# Example 2: typed ops applied to an untyped JSON document
ConfigPatchBody = make_json_patch_body(OperationRegistry.standard())


_USERS: dict[int, User] = {
    1: User(id=1, name="Angela", tags=["admin"]),
    2: User(id=2, name="Pat", tags=["editor", "qa"]),
}

_CONFIGS: MutableMapping[str, JSONValue] = {
    "site": {"title": "Example", "features": {"chat": True}},
    "limits": {"max_users": 5, "trial": False},
}


@app.get("/users/{user_id}")
def get_user(user_id: int) -> User:
    try:
        return _USERS[user_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="user not found") from exc


@app.patch("/users/{user_id}")
def patch_user(user_id: int, patch: UserPatch) -> User:
    user = _USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    updated = patch.apply(user)
    _USERS[user_id] = updated
    return updated


@app.get("/configs/{config_id}")
def get_config(config_id: str) -> JSONValue:
    try:
        return _CONFIGS[config_id]
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="config not found") from exc


@app.patch("/configs/{config_id}")
def patch_config(config_id: str, patch: ConfigPatchBody) -> JSONValue:
    doc = _CONFIGS.get(config_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="config not found")
    updated = patch.apply(doc)
    _CONFIGS[config_id] = updated
    return updated


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}
