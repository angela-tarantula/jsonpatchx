import pytest

from jsonpatchx.builtins import AddOp, RemoveOp, ReplaceOp
from jsonpatchx.exceptions import PatchConflictError
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONValue


def test_addop_root_add_still_works() -> None:
    assert AddOp(path=JSONPointer.parse(""), value={"b": 2}).apply({"a": 1}) == {"b": 2}


def test_removeop_root_delete_rejected() -> None:
    with pytest.raises(PatchConflictError, match="cannot delete the document"):
        RemoveOp(path=JSONPointer.parse("")).apply({"a": 1})


def test_replaceop_root_replace_still_works() -> None:
    assert ReplaceOp(path=JSONPointer.parse(""), value={"b": 2}).apply({"a": 1}) == {
        "b": 2
    }


def test_jsonpatch_root_remove_then_add_is_rejected() -> None:
    payload: list[dict[str, JSONValue]] = [
        {"op": "remove", "path": ""},
        {"op": "add", "path": "", "value": {"a": 1}},
    ]
    patch = JsonPatch(payload)

    with pytest.raises(PatchConflictError, match="cannot delete the document"):
        patch.apply({"a": 1})


def test_jsonpatch_root_replace_still_works() -> None:
    payload: list[dict[str, JSONValue]] = [
        {"op": "replace", "path": "", "value": {"a": 1}},
    ]
    patch = JsonPatch(payload)

    assert patch.apply({"b": 2}) == {"a": 1}
