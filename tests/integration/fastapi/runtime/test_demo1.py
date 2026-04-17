import pytest
from httpx import AsyncClient

from examples.fastapi.demo1 import CustomerPatch
from jsonpatchx import AddOp, JsonPatch, ReplaceOp
from tests.support.http import patch_json

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def test_demo1_confetti_fix(demo1_client: AsyncClient) -> None:
    patch = [
        {"op": "replace", "path": "/email", "value": "morgan@example.com"},
        {"op": "replace", "path": "/marketing_opt_in", "value": True},
    ]

    response = await patch_json(demo1_client, "/customers/2", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["email"] == "morgan@example.com"
    assert payload["marketing_opt_in"] is True


async def test_demo1_vip_sprinkles(demo1_client: AsyncClient) -> None:
    patch = [
        {"op": "add", "path": "/tags/-", "value": "vip"},
        {"op": "replace", "path": "/status", "value": "priority"},
    ]

    response = await patch_json(demo1_client, "/customers/2", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["tags"][-1] == "vip"
    assert payload["status"] == "priority"


async def test_demo1_address_glowup(demo1_client: AsyncClient) -> None:
    patch = [
        {"op": "replace", "path": "/phone", "value": "+1-555-0111"},
        {
            "op": "replace",
            "path": "/address",
            "value": "456 Pine Rd, Seattle, WA",
        },
    ]

    response = await patch_json(demo1_client, "/customers/1", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 1
    assert payload["phone"] == "+1-555-0111"
    assert payload["address"] == "456 Pine Rd, Seattle, WA"


async def test_demo1_accepts_jsonpatch_to_string_payload(
    demo1_client: AsyncClient,
) -> None:
    patch = JsonPatch(
        [
            ReplaceOp(path="/email", value="morgan+string@example.com"),
            ReplaceOp(path="/marketing_opt_in", value=True),
        ]
    )

    response = await demo1_client.patch(
        "/customers/2",
        content=patch.to_string(),  # Uses JsonPatch
        headers={"Content-Type": "application/json-patch+json"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["email"] == "morgan+string@example.com"
    assert payload["marketing_opt_in"] is True


async def test_demo1_accepts_patch_model_dump_json_payload(
    demo1_client: AsyncClient,
) -> None:
    patch = CustomerPatch.model_validate(
        [
            AddOp(path="/tags/-", value="loyal"),
            ReplaceOp(path="/status", value="champion"),
        ]
    )

    response = await demo1_client.patch(
        "/customers/2",
        content=patch.model_dump_json(),  # Uses CustomerPatch
        headers={"Content-Type": "application/json-patch+json"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == 2
    assert payload["tags"][-1] == "loyal"
    assert payload["status"] == "champion"
