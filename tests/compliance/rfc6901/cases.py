from __future__ import annotations

from typing import Final, Self

from pydantic import BaseModel, model_validator


class Case(BaseModel):
    pointer: str
    expected: object | None = None
    fail: str | None = None

    @model_validator(mode="after")
    def _ensure_expected_or_fail(self) -> Self:
        if (
            "expected" not in self.model_fields_set
            and "fail" not in self.model_fields_set
        ):
            raise ValueError("case must include expected or set fail message")
        return self

    @property
    def id(self) -> str:
        if "fail" in self.model_fields_set:
            assert self.fail is not None
            return self.fail
        return repr(self.expected)


DOC: Final = {
    "arr": ["array-item-1", "array-item-2"],
    "": "empty-key",
    "slash/key": "has-slash",
    "tilde~key": "has-tilde",
    "space key": "has-space",
    'quote"key': "has-quote",
    r"backsl\ash": "has-backslash",
    "pct%key": "has-percent",
    "caret^key": "has-caret",
    "pipe|key": "has-pipe",
    r"tab\tkey": "has-tab",
}

# Core RFC 6901 semantics
POINTER_CASES: Final = [
    Case(pointer="", expected=DOC),
    Case(pointer="/arr", expected=["array-item-1", "array-item-2"]),
    Case(pointer="/arr/", fail="invalid pointer"),
    Case(pointer="/nope", fail="missing key"),
    Case(
        pointer="/pct%key/0", fail="strings are not indexable"
    ),  # python-json-pointer fails this
    Case(pointer="/slash~1key/x", fail="missing key"),
    Case(pointer="/arr/0", expected="array-item-1"),
    Case(pointer="/arr/00", fail="invalid index"),
    Case(pointer="/arr/01", fail="invalid index"),
    Case(pointer="/arr/1", expected="array-item-2"),
    Case(pointer="/arr/2", fail="index out of range"),
    Case(pointer="/arr/-1", fail="invalid index"),
    Case(pointer="/arr/nope", fail="invalid index"),
    Case(pointer="/", expected="empty-key"),
    Case(pointer="/slash~1key", expected="has-slash"),
    Case(pointer="/tilde~0key", expected="has-tilde"),
    Case(pointer="/tilde~2key", fail="invalid escape"),
    Case(pointer="/space key", expected="has-space"),
    Case(pointer='/quote"key', expected="has-quote"),
    Case(pointer="/backsl\\ash", expected="has-backslash"),
    Case(pointer="/tab\\tkey", expected="has-tab"),
    Case(pointer="/pct%key", expected="has-percent"),
    Case(pointer="/caret^key", expected="has-caret"),
    Case(pointer="/pipe|key", expected="has-pipe"),
    # python-jsonpath fails these last 3
    Case(pointer="/~arr", fail="non-standard selector"),
    Case(pointer="/#arr", fail="non-standard selector"),
    Case(pointer="/arr/#1", fail="non-standard selector"),
]
