from typing import Literal, override

import pytest

from jsonpatchx import ReplaceOp
from jsonpatchx.exceptions import PatchConflictError, PatchInternalError
from jsonpatchx.pointer import JSONPointer
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONNumber, JSONValue

pytestmark = pytest.mark.integration


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


class ReplaceNumberOp(OperationSchema):
    op: Literal["replace_number"] = "replace_number"
    path: JSONPointer[JSONNumber]
    value: JSONNumber

    @override
    def apply(self, doc: JSONValue) -> JSONValue:
        return ReplaceOp(path=self.path, value=self.value).apply(doc)


def test_custom_op_apply() -> None:
    type Registry = IncrementOp
    patch = JsonPatch(
        [{"op": "increment", "path": "/count", "amount": 2}], registry=Registry
    )
    result = patch.apply({"count": 1})
    assert result == {"count": 3}


def test_custom_op_internal_error_wrapped() -> None:
    type Registry = ExplodeOp
    patch = JsonPatch([{"op": "explode", "path": "/"}], registry=Registry)
    with pytest.raises(PatchInternalError) as exc:
        patch.apply({"a": 1})
    assert exc.value.detail.index == 0
    assert exc.value.detail.cause_type == "ValueError"


def test_replace_number_op_runtime() -> None:

    replaced = JsonPatch(
        [{"op": "replace_number", "path": "/count", "value": 5}],
        registry=ReplaceNumberOp,
    ).apply({"count": 1})
    assert replaced == {"count": 5}

    patch = JsonPatch(
        [{"op": "replace_number", "path": "/count", "value": 5}],
        registry=ReplaceNumberOp,
    )
    with pytest.raises(PatchConflictError):
        patch.apply({"count": "not-a-number"})


@pytest.mark.xfail(reason="Root-targeted ReplaceNumberOp is a known gap for now.")
def test_replace_number_op_runtime_root_number() -> None:

    result = JsonPatch(
        [{"op": "replace_number", "path": "", "value": 2}],
        registry=ReplaceNumberOp,
    ).apply(1)
    assert result == 2
