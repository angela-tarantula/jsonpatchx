from collections.abc import MutableSequence, Sequence
import json
from typing import Literal, override

import pytest
from pytest import Subtests

from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONValue
from jsonpatchx.builtins import AddOp, MoveOp


def test_jsonpatch_sequence_and_dunder_contract(subtests: Subtests) -> None:
    class NoOp(OperationSchema):
        op: Literal["noop"] = "noop"
        path: str

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return doc

    payload = [
        {"op": "noop", "path": "/a"},
        {"op": "noop", "path": "/b"},
        {"op": "move", "from": "/c", "path": "/d"},
    ]
    type Registry = NoOp | MoveOp
    patch = JsonPatch(payload, registry=Registry)

    with subtests.test("ops"):
        assert patch.ops == [
            NoOp(path="/a"),
            NoOp(path="/b"),
            MoveOp(**{"from": "/c", "path": "/d"}),
        ]

    with subtests.test("to_string"):
        assert json.loads(patch.to_string()) == payload

    with subtests.test("sequence"):
        assert isinstance(patch, Sequence)
        assert not isinstance(patch, MutableSequence)
        assert len(patch) == 3
        assert patch[0] == NoOp(path="/a")
        assert patch[:1] == [NoOp(path="/a")]
        assert patch.index(NoOp(path="/a")) == 0
        assert [op for op in patch] == patch.ops
        assert NoOp(path="/b") in patch
        assert patch.count(NoOp(path="/b")) == 1
        assert NoOp(path="/b", other_field="Anything") not in patch

    with subtests.test("str/repr"):
        assert str(patch) == patch.to_string()
        assert repr(patch) == f"JsonPatch({patch.to_string()})"

    type MoveAlias = MoveOp
    type SameRegistry = MoveAlias | NoOp
    same_patch = JsonPatch(payload, registry=SameRegistry)

    type DifferentRegistry = NoOp | MoveOp | AddOp
    different_patch = JsonPatch(payload, registry=DifferentRegistry)

    with subtests.test("eq/hash"):
        assert patch == same_patch
        assert hash(patch) == hash(same_patch)
        assert patch != different_patch
        assert hash(patch) != hash(different_patch)
        assert patch != object()

    with subtests.test("concatenation"):
        combined = patch + same_patch
        assert isinstance(combined, JsonPatch)
        assert len(combined) == 6
        assert [getattr(op, "path") for op in combined] == ["/a", "/b", "/d"] * 2
        with pytest.raises(TypeError):
            # In principle, patches may only be combined if they share the same registry.
            # If desired we can permit patch combinations by taking the registry union when ops don't clash.
            patch + different_patch
