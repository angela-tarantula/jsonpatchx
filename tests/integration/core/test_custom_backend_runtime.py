from typing import Literal, override

import pytest
from jsonpath import JSONPointer as CustomJsonPointer

from jsonpatchx.pointer import JSONPointer
from jsonpatchx.schema import OperationSchema
from jsonpatchx.standard import JsonPatch
from jsonpatchx.types import JSONValue
from tests.support.pointers import DotPointer

pytestmark = pytest.mark.integration


class URIJsonPointer(CustomJsonPointer):
    def __init__(self, pointer: str) -> None:
        super().__init__(pointer, uri_decode=True, unicode_escape=False)


URI_DOC = {
    "space key": "has-space",
    'quote"key': "has-quote",
    r"backsl\ash": "has-backslash",
    "pct%key": "has-percent",
    "caret^key": "has-caret",
    "pipe|key": "has-pipe",
}

URI_CASES = [
    ("/space%20key", "has-space"),
    ("/quote%22key", "has-quote"),
    ("/backsl%5Cash", "has-backslash"),
    ("/pct%25key", "has-percent"),
    ("/caret%5Ekey", "has-caret"),
    ("/pipe%7Ckey", "has-pipe"),
]


@pytest.mark.parametrize(
    ("pointer", "expected"),
    URI_CASES,
    ids=[pointer for pointer, _ in URI_CASES],
)
def test_json_pointer_with_uri_decoding_backend(pointer: str, expected: str) -> None:
    ptr = JSONPointer.parse(pointer, backend=URIJsonPointer)
    assert ptr.get(URI_DOC) == expected


def test_custom_backend_with_registry() -> None:
    class DotRemoveOp(OperationSchema):
        op: Literal["dot-remove"] = "dot-remove"
        path: JSONPointer[JSONValue, DotPointer]

        @override
        def apply(self, doc: JSONValue) -> JSONValue:
            return self.path.remove(doc)

    type Registry = DotRemoveOp
    patch = JsonPatch([{"op": "dot-remove", "path": "a.b"}], registry=Registry)
    result = patch.apply({"a": {"b": 1}})
    assert result == {"a": {}}
