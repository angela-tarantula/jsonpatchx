from __future__ import annotations

import sys
from operator import attrgetter
from typing import Final

import pytest

from jsonpatchx import JSONSelector
from jsonpatchx.exceptions import InvalidJSONSelector
from tests.compliance.rfc9535.case_loader import (
    InvalidSelectorCase,
    ValidCase,
    invalid_selector_cases,
    valid_cases,
)

pytestmark = pytest.mark.integration


PY314_EXPECTED_FAILURES: Final[dict[str, str]] = {
    "functions, match, filter, match function, unicode char class, uppercase": (
        "Python 3.14+ falls back to re for match()/search(), so RFC 9485 "
        "Unicode property classes are not available out of the box"
    ),
    "functions, match, filter, match function, unicode char class negated, uppercase": (
        "Python 3.14+ falls back to re for match()/search(), so RFC 9485 "
        "Unicode property classes are not available out of the box"
    ),
    "functions, match, dot matcher on \\u2028": (
        "Python 3.14+ falls back to re for match()/search(), so dot-matcher "
        "behavior follows re instead of the RFC/I-Regexp path"
    ),
    "functions, match, dot matcher on \\u2029": (
        "Python 3.14+ falls back to re for match()/search(), so dot-matcher "
        "behavior follows re instead of the RFC/I-Regexp path"
    ),
    "functions, search, filter, search function, unicode char class, uppercase": (
        "Python 3.14+ falls back to re for match()/search(), so RFC 9485 "
        "Unicode property classes are not available out of the box"
    ),
    "functions, search, filter, search function, unicode char class negated, uppercase": (
        "Python 3.14+ falls back to re for match()/search(), so RFC 9485 "
        "Unicode property classes are not available out of the box"
    ),
    "functions, search, dot matcher on \\u2028": (
        "Python 3.14+ falls back to re for match()/search(), so dot-matcher "
        "behavior follows re instead of the RFC/I-Regexp path"
    ),
    "functions, search, dot matcher on \\u2029": (
        "Python 3.14+ falls back to re for match()/search(), so dot-matcher "
        "behavior follows re instead of the RFC/I-Regexp path"
    ),
}


def _valid_case_params() -> list[pytest.ParameterSet]:
    params: list[pytest.ParameterSet] = []
    for case in valid_cases():
        marks: list[object] = []
        if sys.version_info >= (3, 14) and case.id in PY314_EXPECTED_FAILURES:
            marks.append(
                pytest.mark.xfail(
                    reason=PY314_EXPECTED_FAILURES[case.id],
                    strict=True,
                )
            )
        params.append(pytest.param(case, id=case.id, marks=marks))
    return params


@pytest.mark.parametrize("case", _valid_case_params())
def test_json_selector_compliance_valid_cases(case: ValidCase) -> None:
    selector = JSONSelector.parse(case.selector)
    assert selector.getall(case.document) in case.expected_results


@pytest.mark.parametrize("case", invalid_selector_cases(), ids=attrgetter("id"))
def test_json_selector_compliance_invalid_selector_cases(
    case: InvalidSelectorCase,
) -> None:
    with pytest.raises(InvalidJSONSelector):
        JSONSelector.parse(case.selector)
