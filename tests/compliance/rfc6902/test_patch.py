from __future__ import annotations

import copy
import json
from operator import attrgetter
from typing import Callable, Final

import pytest
from pydantic import ValidationError
from pytest import Subtests

from jsonpatchx import JsonPatch, StandardRegistry
from jsonpatchx.exceptions import PatchError, PatchInternalError
from jsonpatchx.registry import _RegistrySpec
from tests.compliance.rfc6902.case_loader import (
    FailCase,
    PassCase,
    fail_cases,
    pass_cases,
)

pytestmark = pytest.mark.integration


SKIPPED_CASES: Final = {
    # {skipped_test_case: rationale}
    "duplicate ops": (
        "Duplicate-key handling is delegated to Python's built-in JSON decoder. "
        "JsonPatch.from_string() follows the last-write-wins policy, just like json.loads(). "
        "If you need strict duplicate-key rejection, decode JSON yourself and pass the result to JsonPatch()."
    )
}


type Case = PassCase | FailCase
type PatchBuilder = Callable[[Case], JsonPatch]


def _build_patch_python(case: Case) -> JsonPatch:
    """Build JsonPatch from Python list/dict structures."""
    return JsonPatch(case.patch)


def _build_patch_instantiated(case: Case) -> JsonPatch:
    """Build JsonPatch from instantiated operation models."""
    STANDARD_SPEC = _RegistrySpec.from_typeform(StandardRegistry)
    ops = STANDARD_SPEC.parse_python_patch(case.patch)
    return JsonPatch(ops)


def _build_patch_direct(case: Case) -> JsonPatch:
    """Build JsonPatch directly from JSON string."""
    patch_text = json.dumps(case.patch)
    return JsonPatch.from_string(patch_text)


PATCH_BUILDERS: Final[tuple[tuple[str, PatchBuilder], ...]] = (
    ("direct", _build_patch_direct),
    ("instantiated", _build_patch_instantiated),
    ("python", _build_patch_python),
)


def _case_uses_only_non_root_paths(case: PassCase) -> bool:
    # When JsonPatch.apply(..., inplace=True), in-place mutation is only guaranteed on non-root-targeting patches.
    # This method filters for those patches where that guarantee must be tested.
    return all(op.get("path") != "" for op in case.patch)


def _assert_pass_case_with_builder(
    case: PassCase, build_patch: PatchBuilder, *, inplace: bool
) -> None:
    patch = build_patch(case)

    doc = copy.deepcopy(case.doc)
    assert patch.apply(doc, inplace=inplace) == case.expected
    if inplace:
        if _case_uses_only_non_root_paths(case):
            assert doc == case.expected
        else:
            # inplace=True is only upheld when root isn't replaced
            pass
    else:
        assert doc == case.doc


def _assert_fail_case_with_builder(
    case: FailCase, build_patch: PatchBuilder, *, inplace: bool
) -> None:
    try:
        patch = build_patch(case)
    except Exception as exc:
        assert isinstance(exc, (PatchError, ValidationError))
        assert not isinstance(exc, PatchInternalError), f"Internal error: {exc!r}"
        return

    doc = copy.deepcopy(case.doc)
    with pytest.raises(PatchError) as exc_info:
        patch.apply(doc, inplace=inplace)
    assert not isinstance(exc_info.value, PatchInternalError), (
        f"Internal error {exc_info!r}"
    )
    if not inplace:
        # Patch application is atomic: on failure, no partial changes are applied.
        assert doc == case.doc


@pytest.mark.parametrize("case", pass_cases(), ids=attrgetter("id"))
def test_json_patch_compliance_pass_cases(case: PassCase, subtests: Subtests) -> None:
    if case.id in SKIPPED_CASES:  # pragma: no cover
        pytest.skip(reason=SKIPPED_CASES[case.id])

    for variant, build_patch in PATCH_BUILDERS:
        for inplace in (False, True):
            with subtests.test(variant=variant, inplace=inplace):
                _assert_pass_case_with_builder(case, build_patch, inplace=inplace)


@pytest.mark.parametrize("case", fail_cases(), ids=attrgetter("id"))
def test_json_patch_compliance_fail_cases(case: FailCase, subtests: Subtests) -> None:
    if case.id in SKIPPED_CASES:  # pragma: no cover
        pytest.skip(reason=SKIPPED_CASES[case.id])

    for variant, build_patch in PATCH_BUILDERS:
        for inplace in (False, True):
            with subtests.test(variant=variant, inplace=inplace):
                _assert_fail_case_with_builder(case, build_patch, inplace=inplace)
