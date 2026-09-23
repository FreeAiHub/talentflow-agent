"""Tests that migrations apply, roll back, and still match the models.

These run Alembic for real against a temporary database. A migration that only
works because nobody has run it is not a migration.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from talentflow.config import get_settings
from talentflow.storage.tables import Base

REPO_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_TABLES = {"vacancies", "scored_vacancies", "applications", "runs"}


class Migrations:
    """A configured Alembic environment pointed at a throwaway database."""

    def __init__(self, config: Config, url: str) -> None:
        self.config = config
        self.url = url

    def upgrade(self, revision: str = "head") -> None:
        command.upgrade(self.config, revision)

    def downgrade(self, revision: str = "base") -> None:
        command.downgrade(self.config, revision)

    def tables(self) -> set[str]:
        engine = create_engine(self.url)
        try:
            return set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

    def pending_model_changes(self) -> list[object]:
        """Schema differences Alembic would generate if asked right now."""
        engine = create_engine(self.url)
        try:
            with engine.connect() as connection:
                context = MigrationContext.configure(connection)
                return list(compare_metadata(context, Base.metadata))
        finally:
            engine.dispose()


@pytest.fixture
def migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Migrations:
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    # Settings are cached process-wide, so the override has to be followed by a
    # cache clear or Alembic would read the developer's real database URL.
    monkeypatch.setenv("TALENTFLOW_DATABASE_URL", url)
    get_settings.cache_clear()

    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return Migrations(config, url)


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> Iterator[None]:
    """Keep the cached settings from leaking between tests."""
    yield
    get_settings.cache_clear()


def test_upgrade_head_creates_every_table(migrations: Migrations) -> None:
    migrations.upgrade()

    assert EXPECTED_TABLES.issubset(migrations.tables())


def test_upgrade_records_the_applied_revision(migrations: Migrations) -> None:
    migrations.upgrade()

    assert "alembic_version" in migrations.tables()


def test_downgrade_base_removes_everything(migrations: Migrations) -> None:
    migrations.upgrade()
    migrations.downgrade()

    assert EXPECTED_TABLES.isdisjoint(migrations.tables())


def test_upgrade_downgrade_upgrade_is_stable(migrations: Migrations) -> None:
    """The full cycle must be repeatable, not one-shot."""
    migrations.upgrade()
    migrations.downgrade()
    migrations.upgrade()

    assert EXPECTED_TABLES.issubset(migrations.tables())


def test_upgrade_is_idempotent(migrations: Migrations) -> None:
    migrations.upgrade()
    migrations.upgrade()

    assert EXPECTED_TABLES.issubset(migrations.tables())


def test_migrations_match_the_models(migrations: Migrations) -> None:
    """No drift: editing tables.py without a migration fails here.

    Without this check the schema and the models drift apart silently, and the
    failure surfaces later as a missing column in production.
    """
    migrations.upgrade()

    assert migrations.pending_model_changes() == []
