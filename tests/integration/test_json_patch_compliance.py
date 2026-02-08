from __future__ import annotations

import json
from operator import attrgetter
from pathlib import Path
from typing import Any, Self

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from jsonpatchx import JsonPatch, JSONValue, StandardRegistry
from jsonpatchx.exceptions import PatchError

JSON_PATCH_TESTS_DIR = Path(__file__).resolve().parents[1] / "json-patch-tests"
EXTRA_FIELDS_CASES = {
    "spurious patch properties",
    "A.11.  Ignoring Unrecognized Elements",
}


MISSING = "__MISSING__"


class Case(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    doc: JSONValue
    patch: list[dict[str, Any]]
    expected: JSONValue = MISSING
    error: str | None = None
    comment: str = "<no comment>"
    disabled: bool | None = None

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
    return [Case(**record) for record in load_json_patch_compliance_records()]


@pytest.mark.parametrize("case", cases(), ids=attrgetter("comment"))
def test_json_patch_compliance(case: Case) -> None:
    if case.comment in EXTRA_FIELDS_CASES:
        with pytest.raises(ValidationError):
            JsonPatch(case.patch, registry=StandardRegistry)
        pytest.xfail("library forbids extra fields on operations")

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
