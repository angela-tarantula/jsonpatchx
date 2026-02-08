from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from _pytest.subtests import Subtests
from pydantic import ValidationError

from jsonpatchx import JsonPatch, JSONValue, StandardRegistry
from jsonpatchx.exceptions import PatchError


@dataclass
class Case:
    comment: str | None = None
    doc: JSONValue | None = None
    patch: list[dict[str, Any]] | None = None
    expected: JSONValue | None = None
    error: str | None = None
    disabled: bool | None = None
    tags: list[str] = field(default_factory=list)


EXTRA_FIELDS_CASES = {
    "spurious patch properties",
    "A.11.  Ignoring Unrecognized Elements",
}


def test_json_patch_compliance(
    subtests: Subtests, json_patch_compliance_records: list[dict[str, Any]]
) -> None:
    for record in json_patch_compliance_records:
        case = Case(**record)
        label = case.comment or "<no comment>"
        with subtests.test(label):
            if case.disabled:
                pytest.skip("disabled in json-patch-tests")
            if case.doc is None or case.patch is None:
                pytest.skip("comment-only case")

            if case.comment in EXTRA_FIELDS_CASES:
                with pytest.raises(ValidationError):
                    JsonPatch(case.patch, registry=StandardRegistry)
                pytest.xfail("library forbids extra fields on operations")

            try:
                patch = JsonPatch(case.patch, registry=StandardRegistry)
            except Exception as exc:
                if case.error:
                    assert isinstance(exc, (PatchError, ValidationError))
                    continue
                raise

            if case.error is not None:
                with pytest.raises(PatchError):
                    patch.apply(case.doc)
                continue

            assert case.expected is not None
            assert patch.apply(case.doc) == case.expected
