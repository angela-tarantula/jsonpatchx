from typing import Literal, override

import pytest

from jsonpatchx.exceptions import PatchInternalError
from jsonpatchx.registry import OperationRegistry
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONNumber, JSONPointer, JSONValue


class IncrementOp(OperationSchema):
    op: Literal["increment"] = "increment"
    path: JSONPointer[JSONNumber]
    amount: int = 1

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        current = self.path.get(doc)
        return self.path.add(doc, current + self.amount)


class ExplodeOp(OperationSchema):
    op: Literal["explode"] = "explode"
    path: JSONPointer[JSONValue]

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        raise ValueError("boom")


def test_custom_op_apply() -> None:
    registry = OperationRegistry[IncrementOp]
    patch = JsonPatch(
        [{"op": "increment", "path": "/count", "amount": 2}], registry=registry
    )
    result = patch.apply({"count": 1})
    assert result == {"count": 3}


def test_custom_op_internal_error_wrapped() -> None:
    registry = OperationRegistry[ExplodeOp]
    patch = JsonPatch([{"op": "explode", "path": "/"}], registry=registry)
    with pytest.raises(PatchInternalError) as exc:
        patch.apply({"a": 1})
    assert exc.value.detail.index == 0
    assert exc.value.detail.cause_type == "ValueError"
