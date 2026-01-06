from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from jsonpatchx.exceptions import PatchError
from jsonpatchx.standard import JsonPatch

TESTS_DIR = Path(__file__).resolve().parents[1]
EXTRA_FIELDS_CASES = {
    "spurious patch properties",
    "A.11.  Ignoring Unrecognized Elements",
}
LEADING_ZERO_CASES = {"test with bad array number that has leading zeros"}


def _load_cases(filename: str) -> list[dict[str, Any]]:
    payload = json.loads((TESTS_DIR / filename).read_text())
    return cast(list[dict[str, Any]], payload)


def _apply_case(case: dict[str, Any]) -> None:
    if case.get("disabled"):
        pytest.skip("case disabled in fixture")
    if "patch" not in case:
        pytest.skip("no patch data in case")
    if case.get("comment") in EXTRA_FIELDS_CASES:
        with pytest.raises(ValidationError):
            JsonPatch(case["patch"])
        pytest.xfail("library forbids extra fields on operations")
    if case.get("error") and case.get("comment") in LEADING_ZERO_CASES:
        pytest.xfail("library accepts leading-zero array indices")
    try:
        patch = JsonPatch(case["patch"])
    except Exception as exc:  # parse-time failure
        if "error" in case:
            assert isinstance(exc, (PatchError, ValidationError))
            return
        raise

    if "error" in case:
        with pytest.raises(PatchError):
            patch.apply(case["doc"])
        return

    result = patch.apply(case["doc"])
    if "expected" not in case:
        pytest.skip("no expected output in fixture")
    assert result == case["expected"]


_RFC_CASES = _load_cases("tests.json")
_RFC_IDS = [case.get("comment", f"case-{idx}") for idx, case in enumerate(_RFC_CASES)]

@pytest.mark.parametrize("case", _RFC_CASES, ids=_RFC_IDS)
def test_rfc_examples(case: dict[str, Any]) -> None:
    _apply_case(case)


_SPEC_CASES = _load_cases("spec_tests.json")
_SPEC_IDS = [
    case.get("comment", f"case-{idx}") for idx, case in enumerate(_SPEC_CASES)
]

@pytest.mark.parametrize("case", _SPEC_CASES, ids=_SPEC_IDS)
def test_spec_cases(case: dict[str, Any]) -> None:
    _apply_case(case)
