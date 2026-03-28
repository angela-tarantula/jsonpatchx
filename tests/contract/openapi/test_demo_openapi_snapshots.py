"""
OpenAPI snapshots for end-to-end FastAPI demo applications.

This test verifies that the published OpenAPI docs for demo1-7 remain stable as
examples evolve, including route-helper behavior and example-driven schema output.
"""

import pytest

from examples.loader import Demo, load_snapshot

pytestmark = pytest.mark.contract


def test_demo_openapi_snapshot(contract: Demo) -> None:
    assert contract.app.openapi() == load_snapshot(contract)
