from __future__ import annotations

from typing import cast

import pytest

from examples.loader import (
    DEMO_MAP,
    Demo,
)


@pytest.fixture(params=tuple(DEMO_MAP), ids=lambda demo_id: f"demo{demo_id}")
def contract(request: pytest.FixtureRequest) -> Demo:
    demo_id = cast(str, request.param)
    return DEMO_MAP[demo_id]
