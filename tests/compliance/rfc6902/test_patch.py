from __future__ import annotations

import json
from operator import attrgetter
from typing import Callable, Final

import pytest
from pydantic import ValidationError
from pytest import Subtests

from jsonpatchx import JsonPatch, StandardRegistry
from jsonpatchx.exceptions import PatchError
from jsonpatchx.registry import _RegistrySpec
from tests.compliance.rfc6902.case_loader import Case, cases

pytestmark = pytest.mark.integration


SKIPPED_CASES: Final = {
    # {skipped_test_case: rationale}
    "duplicate ops": (
        "Duplicate-key handling is delegated to the JSON decoder. "
        "JsonPatch.from_string() follows the last-write-wins policy, just like json.loads(). "
        "If you need strict duplicate-key rejection, decode JSON yourself and pass the result to JsonPatch()."
    )
}


type PatchBuilder = Callable[[Case], JsonPatch]


def _build_patch_python(case: Case) -> JsonPatch:
    """Build JsonPatch from Python list/dict structures."""
    return JsonPatch(case.patch, registry=StandardRegistry)


def _build_patch_instantiated(case: Case) -> JsonPatch:
    """Build JsonPatch from instantiated operation models."""
    STANDARD_SPEC = _RegistrySpec.from_typeform(StandardRegistry)
    ops = STANDARD_SPEC.parse_python_patch(case.patch)
    return JsonPatch(ops, registry=StandardRegistry)


def _build_patch_direct(case: Case) -> JsonPatch:
    """Build JsonPatch directly from JSON string."""
    patch_text = json.dumps(case.patch)
    return JsonPatch.from_string(patch_text, registry=StandardRegistry)


PATCH_BUILDERS: Final[tuple[tuple[str, PatchBuilder], ...]] = (
    ("direct", _build_patch_direct),
    ("instantiated", _build_patch_instantiated),
    ("python", _build_patch_python),
)


def _assert_case_with_builder(case: Case, build_patch: PatchBuilder) -> None:
    try:
        patch = build_patch(case)
    except Exception as exc:
        if case.error is not None:
            assert isinstance(exc, (PatchError, ValidationError))
            return
        raise

    if case.error is not None:
        with pytest.raises(PatchError):
            patch.apply(case.doc)
        return
    if "expected" in case.model_fields_set:
        assert patch.apply(case.doc) == case.expected
        return
    pytest.fail(f"invalid case: {case!r}")  # pragma: no cover


@pytest.mark.parametrize("case", cases(), ids=attrgetter("comment"))
def test_json_patch_compliance(case: Case, subtests: Subtests) -> None:
    if case.comment in SKIPPED_CASES:  # pragma: no cover
        pytest.skip(reason=SKIPPED_CASES[case.comment])

    for variant, build_patch in PATCH_BUILDERS:
        with subtests.test(variant=variant):
            _assert_case_with_builder(case, build_patch)
