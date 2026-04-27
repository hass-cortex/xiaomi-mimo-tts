"""Pure-engine test fixtures. Does NOT mock homeassistant.* — engine has no HA imports."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import aiohttp
import pytest
import pytest_asyncio
from aioresponses import aioresponses


@pytest_asyncio.fixture
async def aiohttp_session() -> AsyncGenerator[aiohttp.ClientSession]:
    async with aiohttp.ClientSession() as session:
        yield session


@pytest.fixture
def mock_http() -> aioresponses:
    with aioresponses() as m:
        yield m
