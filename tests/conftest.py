"""Shared pytest fixtures.

The API is exercised through ``httpx.ASGITransport`` rather than
``TestClient``: both the test body and the database session then live in a
single event loop, which avoids an async engine created in one loop being used
from another. That failure mode is intermittent and unpleasant to debug, so it
is designed out rather than worked around.
"""

from collections.abc import AsyncIterator

import httpx
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from talentflow.api.main import app
from talentflow.storage import create_engine, create_sessionmaker, get_session
from talentflow.storage.tables import Base

IN_MEMORY_SQLITE = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """A fresh in-memory database per test, with the schema created."""
    engine = create_engine(IN_MEMORY_SQLITE)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session bound to the per-test database."""
    factory = create_sessionmaker(engine)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def api_client(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client for the app, with the database dependency pointed at the test."""
    factory: async_sessionmaker[AsyncSession] = create_sessionmaker(engine)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _override
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()
