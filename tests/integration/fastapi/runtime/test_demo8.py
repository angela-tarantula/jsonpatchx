import pytest
from httpx import AsyncClient

from tests.support.http import patch_json

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


async def test_demo8_default_selector_op_apply(demo8_client: AsyncClient) -> None:
    patch = [{"op": "toggle_selected_flags", "path": "$.features.*"}]

    response = await patch_json(demo8_client, "/configs/service", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["features"]["chat"] is False
    assert payload["features"]["beta"] is True


async def test_demo8_generic_selector_op_apply(demo8_client: AsyncClient) -> None:
    patch = [{"op": "generic_increment_each", "path": "$.limits.*", "value": 5}]

    response = await patch_json(demo8_client, "/configs/service", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["limits"]["max_users"] == 255
    assert payload["limits"]["retry_budget"] == 8


async def test_demo8_custom_selector_op_apply(demo8_client: AsyncClient) -> None:
    patch = [{"op": "set_selected_flags", "path": "features.*", "value": True}]

    response = await patch_json(demo8_client, "/configs/service", patch)

    assert response.status_code == 200
    payload = response.json()
    assert payload["features"]["chat"] is True
    assert payload["features"]["beta"] is True


async def test_demo8_custom_selector_type_gates_matches(
    demo8_client: AsyncClient,
) -> None:
    patch = [{"op": "set_selected_flags", "path": "limits.*", "value": True}]

    response = await patch_json(demo8_client, "/configs/service", patch)

    assert response.status_code == 409
