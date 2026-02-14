import pytest

from examples.fastapi import demo1
from tests.integration.fastapi_tests.utils import make_client, patch_json

pytestmark = pytest.mark.anyio


async def test_demo1_confetti_fix() -> None:
    patch = [
        {"op": "replace", "path": "/email", "value": "morgan@example.com"},
        {"op": "replace", "path": "/marketing_opt_in", "value": True},
    ]

    async with make_client(demo1.app) as client:
        response = await patch_json(client, "/customers/2", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["email"] == "morgan@example.com"
    assert payload["marketing_opt_in"] is True


async def test_demo1_vip_sprinkles() -> None:
    patch = [
        {"op": "add", "path": "/tags/-", "value": "vip"},
        {"op": "replace", "path": "/status", "value": "priority"},
    ]

    async with make_client(demo1.app) as client:
        response = await patch_json(client, "/customers/2", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["tags"][-1] == "vip"
    assert payload["status"] == "priority"


async def test_demo1_address_glowup() -> None:
    patch = [
        {"op": "replace", "path": "/phone", "value": "+1-555-0111"},
        {
            "op": "replace",
            "path": "/address",
            "value": "456 Pine Rd, Seattle, WA",
        },
    ]

    async with make_client(demo1.app) as client:
        response = await patch_json(client, "/customers/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["phone"] == "+1-555-0111"
    assert payload["address"] == "456 Pine Rd, Seattle, WA"
