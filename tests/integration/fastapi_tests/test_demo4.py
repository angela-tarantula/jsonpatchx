import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from examples.fastapi import demo4

from .utils import make_client, patch_json

pytestmark = pytest.mark.anyio


async def test_demo4_spellbook_midnight_runes() -> None:
    patch = [
        {"op": "replace", "path": "rituals.summon.enabled", "value": True},
        {"op": "increment", "path": "ingredients.moon_salt", "value": 5},
    ]

    async with make_client(demo4.app) as client:
        response = await patch_json(client, "/spellbooks/grimoire", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["rituals"]["summon"]["enabled"] is True
    assert payload["ingredients"]["moon_salt"] == 8


async def test_demo4_apprentice_sparkle_sprint() -> None:
    patch = [
        {"op": "increment", "path": "mana", "value": 20},
        {"op": "append", "path": "sigils", "value": "aurora"},
    ]

    async with make_client(demo4.app) as client:
        response = await patch_json(client, "/apprentices/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["mana"] == 140
    assert payload["sigils"][-1] == "aurora"


async def test_demo4_apprentice_lantern_lesson() -> None:
    patch = [
        {"op": "replace", "path": "name", "value": "Nova"},
        {"op": "append", "path": "sigils", "value": "ember"},
    ]

    async with make_client(demo4.app) as client:
        response = await patch_json(client, "/apprentices/2", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Nova"
    assert payload["sigils"][-1] == "ember"
