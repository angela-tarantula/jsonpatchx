from datetime import datetime, timezone
from typing import Literal

import pytest
from pydantic import BaseModel, ConfigDict

from jsonpatchx.exceptions import PatchValidationError
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.registry import StandardRegistry

pytestmark = pytest.mark.integration


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


class NonUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    title: str


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    at: datetime | Literal["unknown"]  # may cause model_dump() to fail


def test_model_validation_failure() -> None:
    UserPatch = JsonPatchFor[User, StandardRegistry]
    patch = UserPatch.model_validate([{"op": "replace", "path": "/name", "value": 123}])
    with pytest.raises(PatchValidationError):
        patch.apply(User(id=1, name="Ada"))


def test_wrong_model_instance() -> None:
    UserPatch = JsonPatchFor[User, StandardRegistry]
    patch = UserPatch.model_validate(
        [
            {"op": "remove", "path": "/title"},
            {"op": "add", "path": "/name", "value": "Ada"},
        ]
    )
    with pytest.raises(TypeError, match="expects a User instance"):
        patch.apply(NonUser(id=1, title="Dr."))  # type: ignore[arg-type]


def test_model_dump_failure() -> None:
    EventPatch = JsonPatchFor[Event, StandardRegistry]
    patch = EventPatch.model_validate([])

    with pytest.raises(
        PatchValidationError, match="Target model produced non-JSON data for patching"
    ):
        patch.apply(Event(id=1, at=datetime.now(timezone.utc)))


def test_json_body_patch_rejects_non_json_document() -> None:
    ConfigPatch = JsonPatchFor[Literal["Config"], StandardRegistry]
    patch = ConfigPatch.model_validate([])

    with pytest.raises(PatchValidationError, match="Invalid JSON document"):
        patch.apply(object())  # type: ignore[arg-type]
