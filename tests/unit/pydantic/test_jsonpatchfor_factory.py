from typing import Any, Literal, cast, override

import pytest
from pydantic import BaseModel, ConfigDict
from pytest import Subtests

from jsonpatchx.exceptions import InvalidOperationRegistry
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.pydantic import JsonPatchFor
from jsonpatchx.registry import StandardRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.types import JSONValue


class User(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int
    name: str


def test_jsonpatchfor_args() -> None:
    with pytest.raises(TypeError):
        JsonPatchFor[int, StandardRegistry]  # type: ignore[type-var]

    JsonPatchFor[User]
    JsonPatchFor[User, StandardRegistry]
    JsonPatchFor[Literal["Config"]]
    JsonPatchFor[Literal["Config"], StandardRegistry]

    with pytest.raises(InvalidOperationRegistry):
        JsonPatchFor[User, object()]  # type: ignore[misc]
    with pytest.raises(InvalidOperationRegistry):
        JsonPatchFor[Literal["Config"], User]  # type: ignore[type-var]


def test_jsonpatchfor_rejects_invalid_target_forms(subtests: Subtests) -> None:
    with subtests.test("bare string target is rejected"):
        with pytest.raises(TypeError):
            JsonPatchFor["Config", StandardRegistry]  # type: ignore[name-defined]

    with subtests.test("wrong number of generic args is rejected"):
        with pytest.raises(TypeError):
            JsonPatchFor[User, StandardRegistry, StandardRegistry]  # type: ignore[misc]

    with subtests.test("Literal target with multiple args is rejected"):
        with pytest.raises(TypeError):
            JsonPatchFor[Literal["Config1", "Config2"], StandardRegistry]

    with subtests.test("Literal target with non-string arg is rejected"):
        with pytest.raises(TypeError):
            JsonPatchFor[Literal[123], StandardRegistry]  # type: ignore[type-var]


def test_jsonpatchfor_with_custom_registry() -> None:
    class NoOp(OperationSchema):
        op: Literal["noop"] = "noop"

        @override
        def apply(self, doc: JSONValue) -> JSONValue:  # pragma: no cover
            return doc

    type Registry = NoOp
    PatchBody = JsonPatchFor[User, Registry]
    patch = PatchBody.model_validate([{"op": "noop"}])
    assert patch.ops


def test_jsonpatchfor_accepts_registry_type_aliases() -> None:
    class EchoOp(OperationSchema):
        op: Literal["echo-alias"] = "echo-alias"
        path: JSONPointer[JSONValue]
        value: JSONValue

        @override
        def apply(self, doc: JSONValue) -> JSONValue:  # pragma: no cover
            return doc

    class StampOp(OperationSchema):
        op: Literal["stamp"] = "stamp"
        path: JSONPointer[JSONValue]
        value: JSONValue

        @override
        def apply(self, doc: JSONValue) -> JSONValue:  # pragma: no cover
            return doc

    type EchoRegistry = EchoOp
    type StampRegistry = StampOp
    type EchoRegistryAlias = EchoRegistry
    type CombinedRegistry = EchoRegistryAlias | StampRegistry

    PatchFromAlias = JsonPatchFor[User, EchoRegistryAlias]
    parsed_from_alias = PatchFromAlias.model_validate(
        [{"op": "echo-alias", "path": "/name", "value": "ok"}]
    )
    assert type(parsed_from_alias.ops[0]) is EchoOp

    PatchFromUnionAlias = JsonPatchFor[Literal["Config"], CombinedRegistry]
    parsed_from_union_alias = PatchFromUnionAlias.model_validate(
        [{"op": "stamp", "path": "/name", "value": "ok"}]
    )
    assert type(parsed_from_union_alias.ops[0]) is StampOp


def test_jsonpatchfor_metadata_stability(subtests: Subtests) -> None:
    UserPatchDefault = JsonPatchFor[User]
    UserPatch = JsonPatchFor[User, StandardRegistry]
    ConfigPatchDefault = JsonPatchFor[Literal["Config"]]
    ConfigPatch = JsonPatchFor[Literal["Config"], StandardRegistry]
    UserPatchDuplicate = JsonPatchFor[User, StandardRegistry]
    ConfigPatchDuplicate = JsonPatchFor[Literal["Config"], StandardRegistry]

    user_schema_default = UserPatchDefault.model_json_schema()
    user_schema = UserPatch.model_json_schema()
    config_schema_default = ConfigPatchDefault.model_json_schema()
    config_schema = ConfigPatch.model_json_schema()
    user_schema_duplicate = UserPatchDuplicate.model_json_schema()
    config_schema_duplicate = ConfigPatchDuplicate.model_json_schema()

    with subtests.test("model patch class name"):
        assert UserPatchDefault.__name__ == UserPatch.__name__
        assert UserPatch.__name__ == "UserPatchRequest"
        assert UserPatch.__name__ == UserPatchDuplicate.__name__

    with subtests.test("json patch class name"):
        assert ConfigPatchDefault.__name__ == ConfigPatch.__name__
        assert ConfigPatch.__name__ == "ConfigPatchRequest"
        assert ConfigPatch.__name__ == ConfigPatchDuplicate.__name__

    with subtests.test("model patch class doc"):
        assert UserPatch.__doc__ == "Array of patch operations for User."
        assert UserPatch.__doc__ == UserPatchDuplicate.__doc__

    with subtests.test("json patch class doc"):
        assert ConfigPatch.__doc__ == (
            "Discriminated union of patch operations for Config."
        )
        assert ConfigPatch.__doc__ == ConfigPatchDuplicate.__doc__

    with subtests.test("model patch schema title"):
        assert user_schema_default["title"] == user_schema["title"]
        assert user_schema["title"] == "User Patch Request"
        assert user_schema["title"] == user_schema_duplicate["title"]

    with subtests.test("json patch schema title"):
        assert config_schema_default["title"] == config_schema["title"]
        assert config_schema["title"] == "Config Patch Request"
        assert config_schema["title"] == config_schema_duplicate["title"]

    with subtests.test("model patch schema description"):
        assert user_schema_default["description"] == user_schema["description"]
        assert user_schema["description"] == (
            "Array of patch operations for User. "
            "Applied to model_dump() and re-validated against the model schema."
        )
        assert user_schema["description"] == user_schema_duplicate["description"]

    with subtests.test("json patch schema description"):
        assert config_schema_default["description"] == config_schema["description"]
        assert config_schema["description"] == "Array of patch operations for Config."
        assert config_schema["description"] == config_schema_duplicate["description"]


def test_jsonpatchfor_bindings(subtests: Subtests) -> None:
    UserPatch = JsonPatchFor[User, StandardRegistry]
    ConfigPatch = JsonPatchFor[Literal["Config"], StandardRegistry]
    user_patch_registry = getattr(UserPatch, "__registry__")
    config_patch_registry = getattr(ConfigPatch, "__registry__")

    with subtests.test("model variant binds target model"):
        assert getattr(UserPatch, "__target_model__") is User

    with subtests.test("model variant binds registry"):
        assert cast(Any, user_patch_registry).ops

    with subtests.test("json variant binds registry"):
        assert cast(Any, config_patch_registry).ops

    with subtests.test("x-target-model metadata appears with model description"):
        user_schema = UserPatch.model_json_schema()
        assert user_schema["x-target-model"] == "User"
        assert (
            "Applied to model_dump() and re-validated against the model schema."
            in user_schema["description"]
        )
