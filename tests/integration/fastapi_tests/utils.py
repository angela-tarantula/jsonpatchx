from __future__ import annotations

import httpx


def make_client(app: object) -> "httpx.AsyncClient":
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def patch_json(
    client: "httpx.AsyncClient", url: str, patch: list[dict[str, object]]
):
    from jsonpatchx.fastapi import JSON_PATCH_MEDIA_TYPE

    return await client.patch(
        url,
        json=patch,
        headers={"Content-Type": JSON_PATCH_MEDIA_TYPE},
    )
