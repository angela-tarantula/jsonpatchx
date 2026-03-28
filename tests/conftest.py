from __future__ import annotations

import pytest

from tests.support.type_suite import EXAMPLE_VALUES, TYPE_MAPPING, TypeSuite


@pytest.fixture(scope="session")
def suite() -> TypeSuite:
    return TypeSuite(type_map=TYPE_MAPPING, examples=EXAMPLE_VALUES)
