from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError
from pytest import Subtests

from tests.support.type_suite import TypeSuite


def test_json_type_validations(subtests: Subtests, suite: TypeSuite) -> None:
    """Verify that Pydantic TypeAdapters align with suite predicate logic."""
    for json_type in suite.types:
        adapter = TypeAdapter(json_type)

        for example in suite.examples:
            expected_ok = suite.is_compatible(example.value, json_type)
            label = f"{json_type!r} vs {example.label}"

            with subtests.test(label):
                if expected_ok:
                    adapter.validate_python(example.value, strict=True)
                else:
                    with pytest.raises(ValidationError):
                        adapter.validate_python(example.value, strict=True)
