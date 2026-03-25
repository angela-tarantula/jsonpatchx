"""
OpenAPI snapshots for end-to-end FastAPI demo applications.

This test verifies that the published OpenAPI docs for demo1-7 remain stable as
examples evolve, including route-helper behavior and example-driven schema output.
"""

import pytest

from tests.support.openapi_contracts import DEMO_OPENAPI_CONTRACTS, DemoOpenAPIContract

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    "contract",
    DEMO_OPENAPI_CONTRACTS,
    ids=lambda contract: contract.name,
)
def test_demo_openapi_snapshot(contract: DemoOpenAPIContract) -> None:
    expected = contract.snapshot
    actual = contract.app.openapi()
    assert actual == expected
