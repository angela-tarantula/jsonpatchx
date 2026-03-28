from __future__ import annotations

import json
from importlib import resources
from operator import attrgetter
from typing import Any, Final, Self

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from jsonpatchx import JsonPatch, JSONValue, StandardRegistry
from jsonpatchx.exceptions import PatchError
from jsonpatchx.registry import _RegistrySpec

pytestmark = pytest.mark.integration


def load_json_records(*resource_paths: str) -> list[dict[str, Any]]:
    """Load and concatenate JSON object arrays from dotted package.stem paths."""
    records: list[dict[str, Any]] = []
    for resource_path in resource_paths:
        package, stem = resource_path.rsplit(".", maxsplit=1)
        filename = f"{stem}.json"
        data_root = resources.files(package)
        with (data_root / filename).open(encoding="utf8") as fd:
            records.extend(json.load(fd))
    return records


def load_json_patch_compliance_records() -> list[dict[str, Any]]:
    """Return raw compliance records from upstream and jsonpatchx-specific data files."""
    records = load_json_records(
        "tests.compliance.rfc6902.external.tests",
        "tests.compliance.rfc6902.external.spec_tests",
        "tests.compliance.rfc6902.jsonpatchx_tests",
        "tests.compliance.rfc6902.jsonpatchx_nonfinite_tests",
    )

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


class Case(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    doc: JSONValue
    patch: list[dict[str, Any]]
    expected: JSONValue | None = None
    error: str | None = None
    comment: str
    # disregard the 'disabled' flag because jsonpatchx implements handling of these cases

    @model_validator(mode="before")
    @classmethod
    def _fill_comment_with_error(cls, data: object) -> object:
        assert isinstance(data, dict)
        data["comment"] = data.get("comment") or data.get("error") or "<no comment>"
        return data

    @model_validator(mode="after")
    def _ensure_expected_or_error(self) -> Self:
        if (
            "expected" not in self.model_fields_set and self.error is None
        ):  # pragma: no cover
            raise ValueError("case must include expected or error")
        return self


def cases() -> list[Case]:
    return [Case(**record) for record in load_json_patch_compliance_records()]


SKIPPED_CASES: Final = {
    # {skipped_test_case: rationale}
    "duplicate ops": (
        "Duplicate-key handling is delegated to the JSON decoder. "
        "JsonPatch.from_string() follows the last-write-wins policy, just like json.loads(). "
        "If you need strict duplicate-key rejection, decode JSON yourself and pass the result to JsonPatch()."
    )
}

STANDARD_SPEC = _RegistrySpec.from_typeform(StandardRegistry)


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
    elif "expected" in case.model_fields_set:
        assert patch.apply(case.doc) == case.expected
    else:  # pragma: no cover
        pytest.fail("invalid case: {case!r}")


@pytest.mark.parametrize("case", cases(), ids=attrgetter("comment"))
def test_json_patch_compliance_with_instantiated_models(case: Case) -> None:
    if case.comment in SKIPPED_CASES:  # pragma: no cover
        pytest.skip(reason=SKIPPED_CASES[case.comment])

    try:
        ops = STANDARD_SPEC.parse_python_patch(case.patch)
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
    elif "expected" in case.model_fields_set:
        assert patch.apply(case.doc) == case.expected
    else:  # pragma: no cover
        pytest.fail("invalid case: {case!r}")


@pytest.mark.parametrize("case", cases(), ids=attrgetter("comment"))
def test_json_patch_compliance_from_string(case: Case) -> None:
    if case.comment in SKIPPED_CASES:  # pragma: no cover
        pytest.skip(reason=SKIPPED_CASES[case.comment])

    try:
        patch_text = json.dumps(case.patch)
        patch = JsonPatch.from_string(patch_text, registry=StandardRegistry)
    except Exception as exc:
        if case.error is not None:
            assert isinstance(exc, (PatchError, ValidationError))
            return
        raise

    if case.error is not None:
        with pytest.raises(PatchError):
            patch.apply(case.doc)
        return
    elif "expected" in case.model_fields_set:
        assert patch.apply(case.doc) == case.expected
    else:  # pragma: no cover
        pytest.fail("invalid case: {case!r}")
