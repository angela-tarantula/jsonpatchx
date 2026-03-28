from __future__ import annotations

import json
from importlib import resources
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, model_validator

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


class Case(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    doc: JSONValue
    patch: list[dict[str, Any]]
    expected: JSONValue | None = None
    error: str | None = None
    comment: str
    # disregard the 'disabled' flag because JsonPatchX implements these difficult cases

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
