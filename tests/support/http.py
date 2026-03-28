from typing import Any

from httpx import AsyncClient


async def patch_json(client: AsyncClient, url: str, patch: list[dict[str, Any]]):
    return await client.patch(
        url,
        json=patch,
        headers={"Content-Type": "application/json-patch+json"},
    )
