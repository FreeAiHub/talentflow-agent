"""Alembic environment.

The database URL comes from application settings rather than ``alembic.ini``,
so there is exactly one source of truth. Both sync (offline SQL generation) and
async (actual connection) paths are supported.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from talentflow.config import get_settings
from talentflow.storage.db import to_async_url
from talentflow.storage.tables import Base, UTCDateTime

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Render our custom column types as their plain SQLAlchemy equivalent.

    Without this, autogenerate emits ``talentflow.storage.tables.UTCDateTime``
    and forgets to import it, producing a migration that cannot run. The DDL is
    identical either way, so the plain type is the better thing to write down.
    """
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime(timezone=True)"
    return False


def _async_url() -> str:
    return to_async_url(get_settings().database_url)


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting to a database.

    Uses the sync URL form: offline mode only needs a dialect, and the async
    driver would add an unnecessary dependency on a running event loop.
    """
    context.configure(
        url=get_settings().database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_item=render_item,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        render_item=render_item,
        # SQLite cannot ALTER most things in place; batch mode rewrites the
        # table instead, so migrations behave the same on SQLite and Postgres.
        render_as_batch=connection.dialect.name == "sqlite",
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    configuration: dict[str, Any] = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = _async_url()

    connectable = async_engine_from_config(
        configuration, prefix="sqlalchemy.", poolclass=pool.NullPool
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
