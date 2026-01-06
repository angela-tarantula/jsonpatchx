import pytest

from jsonpatchx.exceptions import OperationValidationError, TestOpFailed
from jsonpatchx.standard import JsonPatch


def test_root_add_replace_remove() -> None:
    add_patch = JsonPatch([{"op": "add", "path": "", "value": {"x": 1}}])
    assert add_patch.apply({"a": 1}) == {"x": 1}

    replace_patch = JsonPatch([{"op": "replace", "path": "", "value": [1, 2]}])
    assert replace_patch.apply({"a": 1}) == [1, 2]

    remove_patch = JsonPatch([{"op": "remove", "path": ""}])
    assert remove_patch.apply({"a": 1}) is None


def test_root_copy_move() -> None:
    copy_patch = JsonPatch([{"op": "copy", "from": "/a", "path": ""}])
    assert copy_patch.apply({"a": 1, "b": 2}) == 1

    move_patch = JsonPatch([{"op": "move", "from": "/a", "path": ""}])
    assert move_patch.apply({"a": 1, "b": 2}) == 1


def test_root_test() -> None:
    test_patch = JsonPatch([{"op": "test", "path": "", "value": {"a": 1}}])
    assert test_patch.apply({"a": 1}) == {"a": 1}

    bad_test = JsonPatch([{"op": "test", "path": "", "value": {"a": 2}}])
    with pytest.raises(TestOpFailed):
        bad_test.apply({"a": 1})


def test_invalid_root_move() -> None:
    with pytest.raises(OperationValidationError):
        JsonPatch([{"op": "move", "from": "", "path": "/a"}])
