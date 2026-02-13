import pytest

pytest.importorskip("fastapi")

from examples.fastapi.shared import reset_store


@pytest.fixture(autouse=True)
def _reset_demo_store() -> None:
    reset_store()
    yield
    reset_store()
