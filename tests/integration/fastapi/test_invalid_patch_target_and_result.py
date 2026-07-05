"""
Minimal, deliberately-misconfigured FastAPI app exercising `InvalidPatchTarget`
(500) and `InvalidPatchResult` (422) end-to-end over real HTTP requests.

Both exceptions signal server-side misconfiguration, not bad client input, so
none of the shipped `examples/fastapi` demos naturally trigger them. Each route
below is deliberately broken in one specific way to exercise one raise site.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Literal

import pytest
from fastapi import Body, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel, ConfigDict

from jsonpatchx import AddOp, ReplaceOp
from jsonpatchx.fastapi import install_jsonpatch_error_handlers
from jsonpatchx.pydantic import JsonPatchFor

pytestmark = [pytest.mark.anyio, pytest.mark.integration]


class Event(BaseModel):
    id: int
    at: datetime


class StrictUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


type EventRegistry = ReplaceOp
type StrictUserRegistry = AddOp | ReplaceOp

EventPatch = JsonPatchFor[Event, EventRegistry]
StrictUserPatch = JsonPatchFor[StrictUser, StrictUserRegistry]
DocPatch = JsonPatchFor[Literal["Doc"], EventRegistry]

app = FastAPI()
install_jsonpatch_error_handlers(app)


@app.patch("/events/{event_id}/wrong-instance")
def patch_event_wrong_instance(event_id: int, patch: EventPatch = Body(...)) -> Event:
    # Misconfigured on purpose: hands `.apply()` an object that isn't an Event.
    return patch.apply(StrictUser(id=event_id, name="not an event"))  # type: ignore[arg-type]


@app.patch("/events/{event_id}/non-json-dump")
def patch_event_non_json_dump(event_id: int, patch: EventPatch = Body(...)) -> Event:
    # Misconfigured on purpose: Event.at is a datetime, and model_dump()'s
    # default mode="python" leaves it as a non-JSON Python object.
    return patch.apply(Event(id=event_id, at=datetime.now()))


@app.patch("/docs/{doc_id}/non-json-doc")
def patch_doc_non_json_doc(doc_id: str, patch: DocPatch = Body(...)) -> object:
    # Misconfigured on purpose: hands `.apply()` a "document" that isn't valid
    # JSON, as if the server's own store returned an unserialized value.
    return patch.apply({"created": datetime.now()})


@app.patch("/strict-users/{user_id}")
def patch_strict_user(user_id: int, patch: StrictUserPatch = Body(...)) -> StrictUser:
    return patch.apply(StrictUser(id=user_id, name="Ada"))


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_invalid_patch_target_wrong_model_instance(client: AsyncClient) -> None:
    response = await client.patch(
        "/events/1/wrong-instance",
        json=[{"op": "replace", "path": "/id", "value": 2}],
    )

    assert response.status_code == 500
    assert "expects a Event instance, got StrictUser" in response.json()["detail"]


async def test_invalid_patch_target_non_json_model_dump(client: AsyncClient) -> None:
    response = await client.patch(
        "/events/1/non-json-dump",
        json=[{"op": "replace", "path": "/id", "value": 2}],
    )

    assert response.status_code == 500
    assert "non-JSON data" in response.json()["detail"]


async def test_invalid_patch_target_non_json_document(client: AsyncClient) -> None:
    response = await client.patch(
        "/docs/service/non-json-doc",
        json=[{"op": "replace", "path": "/id", "value": 2}],
    )

    assert response.status_code == 500
    assert "Invalid JSON document" in response.json()["detail"]


async def test_invalid_patch_result_extra_field_rejected(client: AsyncClient) -> None:
    response = await client.patch(
        "/strict-users/1",
        json=[{"op": "add", "path": "/nickname", "value": "Ace"}],
    )

    assert response.status_code == 422
    assert "failed validation for StrictUser" in response.json()["detail"]
