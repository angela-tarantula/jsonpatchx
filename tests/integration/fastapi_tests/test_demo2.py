import pytest

from examples.fastapi import demo2
from tests.integration.fastapi_tests.utils import make_client, patch_json

pytestmark = pytest.mark.anyio


async def test_demo2_player_glitter_boost() -> None:
    patch = [
        {"op": "increment", "path": "/xp", "value": 50},
        {"op": "toggle", "path": "/premium"},
    ]

    async with make_client(demo2.app) as client:
        response = await patch_json(client, "/players/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["xp"] == 1250
    assert payload["premium"] is False


async def test_demo2_player_sparkle_unlock() -> None:
    patch = [
        {"op": "require_min", "path": "/level", "min_value": 5},
        {"op": "append_unique", "path": "/perks", "value": "storm-dash"},
    ]

    async with make_client(demo2.app) as client:
        response = await patch_json(client, "/players/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert "storm-dash" in payload["perks"]


async def test_demo2_player_snack_quest() -> None:
    patch = [
        {"op": "remove_value", "path": "/inventory", "value": "healing_potion"},
        {"op": "increment", "path": "/xp", "value": 25},
    ]

    async with make_client(demo2.app) as client:
        response = await patch_json(client, "/players/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["xp"] == 1225
    assert "healing_potion" not in payload["inventory"]


async def test_demo2_guild_owl_parade() -> None:
    patch = [
        {"op": "append", "path": "/badges", "value": "raid-ready"},
        {"op": "increment", "path": "/max_members", "value": 5},
    ]

    async with make_client(demo2.app) as client:
        response = await patch_json(client, "/guilds/2", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["badges"][-1] == "raid-ready"
    assert payload["max_members"] == 9


async def test_demo2_guild_cozy_welcome() -> None:
    patch = [
        {"op": "enforce_max_len", "path": "/members", "max_path": "/max_members"},
        {"op": "append", "path": "/badges", "value": "candle-lit"},
    ]

    async with make_client(demo2.app) as client:
        response = await patch_json(client, "/guilds/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["badges"][-1] == "candle-lit"
    assert len(payload["members"]) <= payload["max_members"]


async def test_demo2_guild_snug_fit() -> None:
    patch = [
        {"op": "append_unique", "path": "/members", "value": "Nova"},
        {"op": "enforce_max_len", "path": "/members", "max_path": "/max_members"},
    ]

    async with make_client(demo2.app) as client:
        response = await patch_json(client, "/guilds/2", patch)

    assert response.status_code == 422
