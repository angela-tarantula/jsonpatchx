from __future__ import annotations

import copy
import os
from collections.abc import Iterable, MutableMapping, Sequence
from typing import Any, Literal, Self, override

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from jsonpatchx import (
    AddOp,
    JSONValue,
    OperationSchema,
    OperationValidationError,
    PatchConflictError,
    RemoveOp,
    ReplaceOp,
)
from jsonpatchx.exceptions import InvalidJSONPointer
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
    email: str
    tags: list[str] = Field(default_factory=list)
    role: str = "member"
    status: str = "active"
    trial: bool = False
    quota: int = 0


class Team(BaseModel):
    id: int
    name: str
    slug: str
    tags: list[str] = Field(default_factory=list)
    plan: str = "pro"
    region: str = "us-east"
    max_members: int = 0


_SEED_USERS: dict[int, User] = {
    1: User(
        id=1,
        name="Morgan Lee",
        email="morgan@example.com",
        tags=["beta", "newsletter"],
        role="owner",
        trial=False,
        quota=250,
    ),
    2: User(
        id=2,
        name="Jules Park",
        email="jules@example.com",
        tags=["growth", "internal"],
        role="member",
        trial=True,
        quota=75,
    ),
}

_SEED_TEAMS: dict[int, Team] = {
    1: Team(
        id=1,
        name="Core Platform",
        slug="core-platform",
        tags=["backend", "infra"],
        plan="enterprise",
        region="us-west",
        max_members=12,
    ),
    2: Team(
        id=2,
        name="Docs Studio",
        slug="docs-studio",
        tags=["writers", "design"],
        plan="pro",
        region="eu-central",
        max_members=6,
    ),
}

_SEED_CONFIGS: MutableMapping[str, JSONValue] = {
    "site": {
        "title": "Atlas",
        "features": {"chat": True, "list": ["beta", "dark-launch"]},
        "tags": ["internal", "staff"],
    },
    "limits": {"max_users": 250, "trial": True},
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
    model_config = ConfigDict(
        title="Increment operation",
        json_schema_extra={"description": "Increments a numeric field by a value."},
    )

    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    value: JSONNumber = Field(gt=0, multiple_of=5)

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        total = current + self.value
        return AddOp(path=self.path, value=total).apply(doc)


class AppendOp(OperationSchema):
    model_config = ConfigDict(
        title="Append operation",
        json_schema_extra={"description": "Appends a value to an array."},
    )

    op: Literal["append"] = "append"
    path: JSONPointer[JSONArray[JSONValue]]
    value: JSONValue

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, self.value]).apply(doc)


class ExtendOp(OperationSchema):
    model_config = ConfigDict(
        title="Extend operation",
        json_schema_extra={"description": "Extends an array with a list of values."},
    )

    op: Literal["extend"] = "extend"
    path: JSONPointer[JSONArray[JSONValue]]
    values: list[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return AddOp(path=self.path, value=[*current, *self.values]).apply(doc)


class ToggleBoolOp(OperationSchema):
    model_config = ConfigDict(
        title="Toggle operation",
        json_schema_extra={"description": "Toggles a boolean value at a path."},
    )

    op: Literal["toggle"] = "toggle"
    path: JSONPointer[JSONBoolean]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return ReplaceOp(path=self.path, value=not current).apply(doc)


class EnsureObjectOp(OperationSchema):
    model_config = ConfigDict(
        title="Ensure object operation",
        json_schema_extra={
            "description": "Ensures the target path resolves to an object, creating one if missing."
        },
    )

    op: Literal["ensure_object"] = "ensure_object"
    path: JSONPointer[JSONObject[JSONValue]]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        try:
            current = self.path.ptr.resolve(doc)
        except Exception:
            return AddOp(path=self.path, value={}).apply(doc)
        if not isinstance(current, dict):
            raise PatchConflictError(
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
            raise OperationValidationError(
                "pointer 'b' cannot be a child of pointer 'a'"
            )
        if self.b.is_parent_of(self.a):
            raise OperationValidationError(
                "pointer 'a' cannot be a child of pointer 'b'"
            )
        return self

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        value_a = self.a.get(doc)
        value_b = self.b.get(doc)
        if DEMO_UNEXPECTED_ERRORS and value_a == value_b:
            raise RuntimeError("boom")
        doc = AddOp(path=self.a, value=value_b).apply(doc)
        return AddOp(path=self.b, value=value_a).apply(doc)


class RemoveNumberOp(OperationSchema):
    model_config = ConfigDict(
        title="Remove number operation",
        json_schema_extra={"description": "Removes a numeric value at a path."},
    )

    op: Literal["remove_number"] = "remove_number"
    path: JSONPointer[JSONNumber]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return RemoveOp(path=self.path).apply(doc)


class DotPointer(PointerBackend):
    """
    Demonstrative pointer backend using dot-separated paths ("a.b.c").

    Notes:
    - Root pointer is the empty string.
    - No escaping is supported; empty segments are rejected.
    """

    _parts: tuple[str, ...]

    def __init__(self, pointer: str) -> None:
        if pointer == "":
            self._parts = tuple()
            return
        if "." not in pointer:
            self._parts = (pointer,)
        else:
            self._parts = tuple(pointer.split("."))
        if any(part == "" for part in self._parts):
            raise InvalidJSONPointer("invalid dot pointer")

    @property
    @override
    def parts(self) -> Sequence[str]:
        return self._parts

    @classmethod
    @override
    def from_parts(cls, parts: Iterable[Any]) -> Self:
        tokens = [str(p) for p in parts]
        if not tokens:
            return cls("")
        return cls(".".join(tokens))

    @override
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

    @override
    def __str__(self) -> str:
        return ".".join(self._parts)

    @override
    def __hash__(self) -> int:
        return hash(self._parts)


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
