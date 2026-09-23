"""Async database engine and session handling.

The application talks to the database through :func:`get_session`, which is a
FastAPI dependency. Tests override that dependency with their own engine, so
nothing here needs to know it is under test.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from talentflow.config import get_settings

#: Sync driver prefix -> async driver prefix. Settings carry the friendlier
#: sync URL so that tooling which is not async (Alembic's offline mode, a shell
#: `sqlite3`) still works; the application upgrades it here.
_ASYNC_DRIVERS = {
    "sqlite://": "sqlite+aiosqlite://",
    "postgresql://": "postgresql+asyncpg://",
    "postgres://": "postgresql+asyncpg://",
}


def to_async_url(url: str) -> str:
    """Return the async-driver form of a SQLAlchemy database URL.

    URLs that already name an async driver are returned unchanged.
    """
    for sync_prefix, async_prefix in _ASYNC_DRIVERS.items():
        if url.startswith(sync_prefix):
            return async_prefix + url[len(sync_prefix) :]
    return url


def create_engine(url: str | None = None, **kwargs: Any) -> AsyncEngine:
    """Build an async engine for ``url`` (defaults to the configured database)."""
    resolved = to_async_url(url or get_settings().database_url)

    # An in-memory SQLite database lives and dies with its connection, so the
    # pool must hold exactly one connection for anything to persist.
    if ":memory:" in resolved:
        kwargs.setdefault("poolclass", StaticPool)
        kwargs.setdefault("connect_args", {"check_same_thread": False})

    engine = create_async_engine(resolved, future=True, **kwargs)
    _enable_sqlite_foreign_keys(engine)
    return engine


def _enable_sqlite_foreign_keys(engine: AsyncEngine) -> None:
    """SQLite ignores foreign keys unless asked, per connection.

    Without this, ``ondelete="CASCADE"`` silently does nothing and orphaned
    rows accumulate.
    """
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_connection: Any, _record: Any) -> None:  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def create_sessionmaker(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory bound to ``engine``."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Process-wide engine, created on first use."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Process-wide session factory, created on first use."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = create_sessionmaker(get_engine())
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session per request."""
    async with get_sessionmaker()() as session:
        yield session


async def dispose_engine() -> None:
    """Close pooled connections. Called on application shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
