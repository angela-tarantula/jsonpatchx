from __future__ import annotations

from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from examples.loader import DEMO_MAP, reset_demo_store


def make_client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
async def demo1_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(DEMO_MAP["1"].app) as client:
        yield client


@pytest.fixture
async def demo2_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(DEMO_MAP["2"].app) as client:
        yield client


@pytest.fixture
async def demo3_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(DEMO_MAP["3"].app) as client:
        yield client


@pytest.fixture
async def demo4_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(DEMO_MAP["4"].app) as client:
        yield client


@pytest.fixture
async def demo5_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(DEMO_MAP["5"].app) as client:
        yield client


@pytest.fixture
async def demo6_client() -> AsyncGenerator[AsyncClient]:
    async with make_client(DEMO_MAP["6"].app) as client:
        yield client


@pytest.fixture(autouse=True)
def reset_demo_store_fixture() -> Generator[None]:
    reset_demo_store()
    yield
    reset_demo_store()
