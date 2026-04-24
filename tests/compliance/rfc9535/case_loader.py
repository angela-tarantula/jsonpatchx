from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jsonpatchx import JSONValue

_CTS_JSON = Path(__file__).with_name("external") / "cts.json"


def load_jsonpath_compliance_records() -> list[dict[str, Any]]:
    """Return raw RFC 9535 compliance records from the official cts.json file."""
    payload = json.loads(_CTS_JSON.read_text(encoding="utf8"))
    return payload["tests"]


class _BaseCase(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    name: str
    selector: str
    tags: list[str] = Field(default_factory=list)

    @property
    def id(self) -> str:
        return self.name


class ValidCase(_BaseCase):
    document: JSONValue
    result: list[JSONValue] | None = None
    results: list[list[JSONValue]] | None = None
    result_paths: list[str] | None = None
    results_paths: list[list[str]] | None = None

    @model_validator(mode="after")
    def _validate_expected_results(self) -> Self:
        has_result = self.result is not None
        has_results = self.results is not None
        if has_result == has_results:
            raise ValueError(
                "valid RFC 9535 case must define exactly one of result or results"
            )
        return self

    @property
    def expected_results(self) -> list[list[JSONValue]]:
        if self.result is not None:
            return [self.result]
        assert self.results is not None
        return self.results


class InvalidSelectorCase(_BaseCase):
    invalid_selector: Literal[True]


def _split_cases(
    records: list[dict[str, Any]],
) -> tuple[list[ValidCase], list[InvalidSelectorCase]]:
    valid: list[ValidCase] = []
    invalid: list[InvalidSelectorCase] = []

    for record in records:
        if record.get("invalid_selector") is True:
            invalid.append(InvalidSelectorCase(**record))
        else:
            valid.append(ValidCase(**record))

    return valid, invalid


def valid_cases() -> list[ValidCase]:
    records = load_jsonpath_compliance_records()
    valid, _ = _split_cases(records)
    return valid


def invalid_selector_cases() -> list[InvalidSelectorCase]:
    records = load_jsonpath_compliance_records()
    _, invalid = _split_cases(records)
    return invalid
