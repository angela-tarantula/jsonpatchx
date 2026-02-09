from typing import Final, Self

import pytest
from jsonpath import JSONPointer as CustomJsonPointer
from pydantic import BaseModel, model_validator

from jsonpatchx import JSONPointer


class URIJsonPointer(CustomJsonPointer):
    # NOTE: investigate functools.partial feasibility
    def __init__(self, pointer) -> None:
        super().__init__(pointer, uri_decode=True)


MISSING = "__MISSING__"


class Case(BaseModel):
    pointer: str
    expected: object = MISSING
    fail: bool = False

    @model_validator(mode="after")
    def _ensure_expected_or_fail(self) -> Self:
        if self.expected == MISSING and not self.fail:
            raise ValueError("case must include expected or set fail=True")
        return self


DOC: Final = {
    "arr": ["x", "y"],
    "": "empty-key",
    "slash/key": "has-slash",
    "tilde~key": "has-tilde",
    "space key": "has-space",
    'quote"key': "has-quote",
    r"back\slash": "has-backslash",
    "pct%key": "has-percent",
    "caret^key": "has-caret",
    "pipe|key": "has-pipe",
}

# Core RFC 6901 semantics
POINTER_CASES = [
    Case(pointer="", expected=DOC),
    Case(pointer="/arr", expected=["x", "y"]),
    Case(pointer="/arr/", fail=True),
    Case(pointer="/nope", fail=True),
    Case(pointer="/pct%key/0", fail=True),
    Case(pointer="/slash~1key/x", fail=True),
    Case(pointer="/arr/0", expected="x"),
    Case(pointer="/arr/00", fail=True),
    Case(pointer="/arr/01", fail=True),
    Case(pointer="/arr/1", expected="y"),
    Case(pointer="/arr/2", fail=True),
    Case(pointer="/arr/-1", fail=True),
    Case(pointer="/arr/nope", fail=True),
    Case(pointer="/", expected="empty-key"),
    Case(pointer="/slash~1key", expected="has-slash"),
    Case(pointer="/tilde~0key", expected="has-tilde"),
    Case(pointer="/tilde~2key", fail=True),
    Case(pointer="/space key", expected="has-space"),
    Case(pointer='/quote"key', expected="has-quote"),
    Case(pointer=r"/back\slash", expected="has-backslash"),
    Case(pointer="/pct%key", expected="has-percent"),
    Case(pointer="/caret^key", expected="has-caret"),
    Case(pointer="/pipe|key", expected="has-pipe"),
    Case(pointer="/~arr", fail=True),
    Case(pointer="/#arr", fail=True),
    Case(pointer="/arr/#1", fail=True),
]


URI_CASES: Final = [
    Case(pointer="/space%20key", expected="has-space"),
    Case(pointer="/quote%22key", expected="has-quote"),
    Case(pointer="/back%5Cslash", expected="has-backslash"),
    Case(pointer="/pct%25key", expected="has-percent"),
    Case(pointer="/caret%5Ekey", expected="has-caret"),
    Case(pointer="/pipe%7Ckey", expected="has-pipe"),
]


@pytest.mark.parametrize("case", POINTER_CASES)  # NOTE: give IDs
def test_json_pointer_core(case: Case) -> None:
    if not case.fail:
        ptr = JSONPointer.parse(case.pointer)
        assert ptr.get(DOC) == case.expected
    else:
        with pytest.raises(Exception):
            ptr = JSONPointer.parse(case.pointer)
            print(ptr.get(DOC))


@pytest.mark.parametrize("case", URI_CASES)
def test_json_pointer_with_uri_decoding(case: Case) -> None:
    if not case.fail:
        ptr = JSONPointer.parse(case.pointer, backend=URIJsonPointer)
        assert ptr.get(DOC) == case.expected
    else:
        with pytest.raises(Exception):
            ptr = JSONPointer.parse(case.pointer, backend=URIJsonPointer)
            print(ptr.get(DOC))
