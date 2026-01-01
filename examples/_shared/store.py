from __future__ import annotations

import copy
from collections.abc import MutableMapping

from jsonpatch.types import JSONValue

from .schemas import Team, User

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
