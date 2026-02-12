"""
Test json-patch-x against an external compliance test suite.

The json-patch-tests submodule is located in /tests/cts.
After a git clone, run `git submodule update --init` from the root of the repository.
"""

from __future__ import annotations

import importlib.resources as resources
import json
from operator import attrgetter
from typing import Any, Final, Self

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from jsonpatchx import JsonPatch, JSONValue, StandardRegistry
from jsonpatchx.exceptions import PatchError

JSON_PATCH_TESTS_DIR = resources.files("tests") / "cts"

SKIPPED_CASES: Final = {
    # {skipped_test_case: rationale}
    "duplicate ops": (
        "Duplicate-key handling is delegated to the JSON decoder. "
        "JsonPatch.from_string() follows the last-write-wins policy, just like json.loads(). "
        "If you need strict duplicate-key rejection, decode JSON yourself and pass the result to JsonPatch()."
    )
}


MISSING = "__MISSING__"


class Case(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    doc: JSONValue
    patch: list[dict[str, Any]]
    expected: JSONValue = MISSING
    error: str | None = None
    comment: str
    # disregard the 'disabled' flag because json-patch-x implements handling of these cases

    @model_validator(mode="before")
    @classmethod
    def _fill_comment_with_error(cls, data: object) -> object:
        if isinstance(data, dict):
            data["comment"] = data.get("comment") or data.get("error") or "<no comment>"
        return data

    @model_validator(mode="after")
    def _ensure_expected_or_error(self) -> Self:
        if self.expected == MISSING and self.error is None:
            raise ValueError("case must include expected or error")
        return self


def load_json_patch_compliance_records() -> list[dict[str, Any]]:
    """Return raw json-patch-tests records (tests.json + spec_tests.json)."""
    records: list[dict[str, Any]] = []
    for filename in ("tests.json", "spec_tests.json"):
        with (JSON_PATCH_TESTS_DIR / filename).open(encoding="utf8") as fd:
            records.extend(json.load(fd))

    # fix a bug in the compliance records
    for record in records:
        if record.get("comment") == "Whole document" and "expected" not in record:
            # this record is missing "expected":
            # {
            #     "comment": "Whole document",
            #     "doc": { "foo": 1 },
            #     "patch": [{"op": "test", "path": "", "value": {"foo": 1}}],
            #     "disabled": true
            # }
            record["expected"] = record["doc"]
    return records


def cases() -> list[Case]:
    return [Case(**record) for record in load_json_patch_compliance_records()] + [
        Case(
            doc=[1, 2, 3],
            patch=[{"op": "replace", "path": "", "value": "something else"}],
            expected="something else",
            comment="root replacement",
        ),
        Case(
            doc={"a": 1, "b": 2},
            patch=[{"op": "test", "path": "", "value": {"b": 2, "a": 1}}],
            expected={"a": 1, "b": 2},
            comment="test at root",
        ),
        Case(
            doc={"a": 1, "b": 2},
            patch=[{"op": "copy", "from": "/a", "path": ""}],
            expected=1,
            comment="copy to root",
        ),
        Case(
            doc={"a": 1, "b": 2},
            patch=[{"op": "move", "from": "/a", "path": ""}],
            expected=1,
            comment="move to root",
        ),
        Case(
            doc={"foo": {"bar": 1}},
            patch=[{"op": "move", "from": "/foo", "path": "/foo/bar"}],
            error="move op should reject parent->child path",
            comment="move parent to child rejected",
        ),
        Case(
            doc=[1, 2, 3],
            patch=[{"op": "remove", "path": ""}],
            expected=None,
            comment=(
                'RFC 6901 defines "" as a pointer to the whole document. RFC 6902 models patching as producing a '
                "'resulting document' after each successful operation, which implies that any successful operation yields "
                "another JSON value/document. RFC 6902 does not explicitly specify the behavior of remove at the root; "
                "this implementation treats it as producing null (Python None), preserving closure and composability. "
                "Users who prefer to forbid root removal can enforce that as an additional constraint."
            ),
        ),
        Case(
            doc={"foo": "should-not-be-indexable"},
            patch=[{"op": "copy", "from": "/foo/0", "path": "/bar"}],
            error="strings should not be indexible in JSON as they are in Python",
            comment="strings can't be indexed",
        ),
    ]


@pytest.mark.parametrize("case", cases(), ids=attrgetter("comment"))
def test_json_patch_compliance(case: Case) -> None:
    if case.comment in SKIPPED_CASES:  # pragma: no cover
        pytest.skip(reason=SKIPPED_CASES[case.comment])

    try:
        patch = JsonPatch(case.patch, registry=StandardRegistry)
    except Exception as exc:
        if case.error is not None:
            assert isinstance(exc, (PatchError, ValidationError))
            return
        raise

    if case.error is not None:
        with pytest.raises(PatchError):
            patch.apply(case.doc)
        return
    elif case.expected != MISSING:
        assert patch.apply(case.doc) == case.expected
    else:  # pragma: no cover
        pytest.fail("invalid case: {case!r}")


@pytest.mark.parametrize("case", cases(), ids=attrgetter("comment"))
def test_json_patch_compliance_with_instantiated_models(case: Case) -> None:
    if case.comment in SKIPPED_CASES:  # pragma: no cover
        pytest.skip(reason=SKIPPED_CASES[case.comment])

    try:
        ops = StandardRegistry.parse_python_patch(case.patch)
        patch = JsonPatch(ops, registry=StandardRegistry)
    except Exception as exc:
        if case.error is not None:
            assert isinstance(exc, (PatchError, ValidationError))
            return
        raise

    if case.error is not None:
        with pytest.raises(PatchError):
            patch.apply(case.doc)
        return
    elif case.expected != MISSING:
        assert patch.apply(case.doc) == case.expected
    else:  # pragma: no cover
        pytest.fail("invalid case: {case!r}")
