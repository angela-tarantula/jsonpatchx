import pytest

from examples.fastapi import demo3
from tests.integration.fastapi_tests.utils import make_client, patch_json

pytestmark = pytest.mark.anyio


async def test_demo3_rocket_boost() -> None:
    patch = [
        {"op": "increment", "path": "/limits/max_users", "value": 50},
        {"op": "toggle", "path": "/features/chat"},
    ]

    async with make_client(demo3.app) as client:
        response = await patch_json(client, "/configs/service", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["limits"]["max_users"] == 300
    assert payload["features"]["chat"] is False


async def test_demo3_tag_and_seal() -> None:
    patch = [
        {"op": "ensure_object", "path": "/features"},
        {"op": "append", "path": "/tags", "value": "beta"},
    ]

    async with make_client(demo3.app) as client:
        response = await patch_json(client, "/configs/service", patch)

    assert response.status_code == 200
    payload = response.json()
    assert "beta" in payload["tags"]
    assert isinstance(payload["features"], dict)


async def test_demo3_shuffle_switch() -> None:
    patch = [
        {"op": "swap", "a": "/service_name", "b": "/features/chat"},
        {"op": "toggle", "path": "/features/chat"},
    ]

    async with make_client(demo3.app) as client:
        response = await patch_json(client, "/configs/service", patch)

    assert response.status_code == 409


async def test_demo3_oops_expected() -> None:
    patch = [
        {"op": "ensure_object", "path": "/features"},
        {"op": "remove_number", "path": "/service_name"},
    ]

    async with make_client(demo3.app) as client:
        response = await patch_json(client, "/configs/service", patch)

    assert response.status_code == 409
