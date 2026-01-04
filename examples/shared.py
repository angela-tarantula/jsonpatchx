from __future__ import annotations

import copy
import os
from collections.abc import Iterable, MutableMapping, Sequence
from typing import Any, Literal, Self

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from jsonpatchx import (
    AddOp,
    InvalidOperationSchema,
    JSONValue,
    OperationSchema,
    PatchApplicationError,
    RemoveOp,
    ReplaceOp,
)
from jsonpatchx.fastapi import JSON_PATCH_MEDIA_TYPE, install_jsonpatch_error_handlers
from jsonpatchx.types import (
    JSONArray,
    JSONBoolean,
    JSONNumber,
    JSONObject,
    JSONPointer,
    PointerBackend,
)

DEMO_UNEXPECTED_ERRORS = os.getenv("JSONPATCH_DEMO_UNEXPECTED_ERRORS", "1") != "0"


def create_app(*, title: str, description: str, version: str = "0.1.0") -> FastAPI:
    app = FastAPI(title=title, description=description, version=version)
    install_jsonpatch_error_handlers(app)

    @app.get("/", include_in_schema=False)
    def _root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


class User(BaseModel):
    id: int
    name: str
    tags: list[str] = Field(default_factory=list)
    trial: bool = False
    quota: int = 0


class Team(BaseModel):
    id: int
    name: str
    tags: list[str] = Field(default_factory=list)
    max_members: int = 0


_SEED_USERS: dict[int, User] = {
    1: User(id=1, name="Angela", tags=["admin"], trial=False, quota=5),
    2: User(id=2, name="Pat", tags=["editor", "qa"], trial=True, quota=2),
}

_SEED_TEAMS: dict[int, Team] = {
    1: Team(id=1, name="Core", tags=["backend"], max_members=5),
    2: Team(id=2, name="Docs", tags=["writers"], max_members=3),
}

_SEED_CONFIGS: MutableMapping[str, JSONValue] = {
    "site": {
        "title": "Example",
        "features": {"chat": True, "list": []},
        "tags": ["admin"],
    },
    "limits": {"max_users": 5, "trial": False},
}

_USERS: dict[int, User] = copy.deepcopy(_SEED_USERS)
_TEAMS: dict[int, Team] = copy.deepcopy(_SEED_TEAMS)
_CONFIGS: MutableMapping[str, JSONValue] = copy.deepcopy(_SEED_CONFIGS)


def reset_store() -> None:
    _USERS.clear()
    _USERS.update(copy.deepcopy(_SEED_USERS))
    _TEAMS.clear()
    _TEAMS.update(copy.deepcopy(_SEED_TEAMS))
    _CONFIGS.clear()
    _CONFIGS.update(copy.deepcopy(_SEED_CONFIGS))


def get_user(user_id: int) -> User | None:
    return _USERS.get(user_id)


def save_user(user_id: int, user: User) -> None:
    _USERS[user_id] = user


def get_team(team_id: int) -> Team | None:
    return _TEAMS.get(team_id)


def save_team(team_id: int, team: Team) -> None:
    _TEAMS[team_id] = team


def get_config(config_id: str) -> JSONValue | None:
    return _CONFIGS.get(config_id)


def save_config(config_id: str, doc: JSONValue) -> None:
    _CONFIGS[config_id] = doc


class IncrementOp(OperationSchema):
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    value: JSONNumber = Field(gt=0, multiple_of=5)

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        total = current + self.value
        return AddOp(path=self.path, value=total).apply(doc)


class AppendOp(OperationSchema):
    op: Literal["append"] = "append"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, self.value]).apply(doc)


class ExtendOp(OperationSchema):
    op: Literal["extend"] = "extend"
    path: JSONPointer[JSONArray[JSONValue]]
    values: list[JSONValue]

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, *self.values]).apply(doc)


class ToggleBoolOp(OperationSchema):
    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=not current).apply(doc)


class EnsureObjectOp(OperationSchema):
    op: Literal["ensure_object"] = "ensure_object"
    path: JSONPointer[JSONObject[JSONValue]]

    def apply(self, doc: JSONValue) -> JSONValue:
        try:
            current = self.path.ptr.resolve(doc)
        except Exception:
            return AddOp(path=self.path, value={}).apply(doc)
        if not isinstance(current, dict):
            raise PatchApplicationError(
                f"expected object at {str(self.path)!r}, got {type(current).__name__}"
            )
        return doc


class SwapOp(OperationSchema):
    model_config = ConfigDict(
        title="Swap operation",
        json_schema_extra={
            "description": (
                "Swaps the values at paths a and b. "
                "Paths a and b may not be proper prefixes of each other."
            )
        },
    )

    op: Literal["swap"] = "swap"
    a: JSONPointer[JSONValue]
    b: JSONPointer[JSONValue]

    @model_validator(mode="after")
    def _reject_proper_prefixes(self) -> Self:
        if self.a.is_parent_of(self.b):
            raise InvalidOperationSchema("pointer 'b' cannot be a child of pointer 'a'")
        if self.b.is_parent_of(self.a):
            raise InvalidOperationSchema("pointer 'a' cannot be a child of pointer 'b'")
        return self

    def apply(self, doc: JSONValue) -> JSONValue:
        value_a = self.a.get(doc)
        value_b = self.b.get(doc)
        if DEMO_UNEXPECTED_ERRORS and value_a == value_b:
            raise RuntimeError("boom")
        doc = AddOp(path=self.a, value=value_b).apply(doc)
        return AddOp(path=self.b, value=value_a).apply(doc)


class RemoveNumberOp(OperationSchema):
    op: Literal["remove_number"] = "remove_number"
    path: JSONPointer[JSONNumber]

    def apply(self, doc: JSONValue) -> JSONValue:
        return RemoveOp(path=self.path).apply(doc)


class DotPointer(PointerBackend):
    """
    Demonstrative pointer backend using dot-separated paths ("a.b.c").

    Notes:
    - Root pointer is the empty string.
    - No escaping is supported; empty segments are rejected.
    """

    def __init__(self, pointer: str) -> None:
        if pointer == "":
            self._parts = tuple()
            return
        if "." not in pointer:
            parts = (pointer,)
        else:
            parts = tuple(pointer.split("."))
        if any(part == "" for part in parts):
            raise ValueError("invalid dot pointer")
        self._parts = parts

    @property
    def parts(self) -> Sequence[str]:
        return self._parts

    @classmethod
    def from_parts(cls, parts: Iterable[Any]) -> Self:
        tokens = [str(p) for p in parts]
        if not tokens:
            return cls("")
        return cls(".".join(tokens))

    def resolve(self, doc: Any) -> Any:
        cur = doc
        for part in self._parts:
            if isinstance(cur, dict):
                cur = cur[part]
            elif isinstance(cur, list):
                if not part.isdigit():
                    raise KeyError("invalid list index")
                idx = int(part)
                cur = cur[idx]
            else:
                raise KeyError("non-container")
        return cur

    def __str__(self) -> str:
        return ".".join(self._parts)


__all__ = [
    "AddOp",
    "AppendOp",
    "EnsureObjectOp",
    "ExtendOp",
    "IncrementOp",
    "JSON_PATCH_MEDIA_TYPE",
    "RemoveNumberOp",
    "SwapOp",
    "ToggleBoolOp",
    "create_app",
    "get_config",
    "get_team",
    "get_user",
    "save_config",
    "save_team",
    "save_user",
    "DotPointer",
    "Team",
    "User",
]
