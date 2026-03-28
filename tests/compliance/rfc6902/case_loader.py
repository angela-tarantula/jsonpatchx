from __future__ import annotations

import json
from importlib import resources
from typing import Any, override

from pydantic import BaseModel, ConfigDict

from jsonpatchx import JSONValue


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

    # Fix an upstream fixture missing "expected" for a non-mutating test op.
    for record in records:
        if record.get("comment") == "Whole document" and "expected" not in record:
            record["expected"] = record["doc"]
    return records


class _BaseCase(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    doc: JSONValue
    patch: list[dict[str, Any]]
    comment: str | None = None
    # Disregard the upstream 'disabled' flag: JsonPatchX implements those difficult cases.

    @property
    def id(self) -> str:
        if self.comment:
            return self.comment
        return "<no id>"


class PassCase(_BaseCase):
    expected: JSONValue


class FailCase(_BaseCase):
    error: str

    @property
    @override
    def id(self) -> str:
        if self.comment:
            return self.comment
        if self.error:
            return self.error
        return "<no id>"


def _split_cases(
    records: list[dict[str, Any]],
) -> tuple[list[PassCase], list[FailCase]]:
    passing: list[PassCase] = []
    failing: list[FailCase] = []

    for record in records:
        if "expected" in record:
            passing.append(PassCase(**record))
        elif record.get("error") is not None:
            failing.append(FailCase(**record))
        else:  # pragma: no cover
            raise ValueError(
                f"compliance record must include expected or error: {record!r}"
            )

    return passing, failing


def pass_cases() -> list[PassCase]:
    records = load_json_patch_compliance_records()
    passing, _ = _split_cases(records)
    return passing


def fail_cases() -> list[FailCase]:
    records = load_json_patch_compliance_records()
    _, failing = _split_cases(records)
    return failing


def all_cases() -> list[PassCase | FailCase]:
    records = load_json_patch_compliance_records()
    passing, failing = _split_cases(records)
    return [*passing, *failing]
