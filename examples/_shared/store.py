from __future__ import annotations

import copy
from collections.abc import MutableMapping

from jsonpatch.types import JSONValue

from .schemas import User

_SEED_USERS: dict[int, User] = {
    1: User(id=1, name="Angela", tags=["admin"], trial=False, quota=5),
    2: User(id=2, name="Pat", tags=["editor", "qa"], trial=True, quota=2),
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
_CONFIGS: MutableMapping[str, JSONValue] = copy.deepcopy(_SEED_CONFIGS)


def reset_store() -> None:
    _USERS.clear()
    _USERS.update(copy.deepcopy(_SEED_USERS))
    _CONFIGS.clear()
    _CONFIGS.update(copy.deepcopy(_SEED_CONFIGS))


def get_user(user_id: int) -> User | None:
    return _USERS.get(user_id)


def save_user(user_id: int, user: User) -> None:
    _USERS[user_id] = user


def get_config(config_id: str) -> JSONValue | None:
    return _CONFIGS.get(config_id)


def save_config(config_id: str, doc: JSONValue) -> None:
    _CONFIGS[config_id] = doc
