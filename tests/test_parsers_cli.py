"""Tests for the ``python -m talentflow.parsers`` command line entry point.

The command is exercised for real — its own event loop, its own engine — so the
test proves what lands in the database, not what the code intends to do (#40).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select

from talentflow.config import get_settings
from talentflow.models import Vacancy
from talentflow.parsers.__main__ import main
from talentflow.storage import create_engine, create_sessionmaker
from talentflow.storage.tables import Base, VacancyRow


def vacancy(vacancy_id: str, **overrides: Any) -> Vacancy:
    data: dict[str, Any] = {
        "id": vacancy_id,
        "title": f"Vacancy {vacancy_id}",
        "company": "Acme",
        "url": f"https://djinni.co/jobs/{vacancy_id}-x/",
        "source": "djinni",
        "description": "Build APIs with FastAPI.",
        "posted_at": datetime(2026, 9, 23, tzinfo=UTC),
    }
    data.update(overrides)
    return Vacancy.model_validate(data)


class FakeParser:
    """Stands in for DjinniParser: no network, a fixed listing."""

    def __init__(self, *, limit: int = 50, **_: Any) -> None:
        self._vacancies = [vacancy("1"), vacancy("2")]

    async def collect(self) -> list[Vacancy]:
        return self._vacancies


async def _create_schema(url: str) -> None:
    engine = create_engine(url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()


async def _count_vacancies(url: str) -> int:
    """Read the database through a fresh engine: what the command actually wrote."""
    engine = create_engine(url)
    factory = create_sessionmaker(engine)
    try:
        async with factory() as session:
            result = await session.execute(select(func.count()).select_from(VacancyRow))
            return int(result.scalar_one())
    finally:
        await engine.dispose()


@pytest.fixture
def cli_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """A file-backed database the command finds through the settings.

    In-memory SQLite would not do: the command opens its own connection, so the
    schema and the rows have to outlive any single engine.
    """
    url = f"sqlite:///{tmp_path / 'cli.db'}"
    # Settings are cached process-wide, so the override has to be followed by a
    # cache clear or the command would read the developer's real database URL.
    monkeypatch.setenv("TALENTFLOW_DATABASE_URL", url)
    monkeypatch.setattr("talentflow.parsers.__main__.SOURCES", {"djinni": FakeParser})
    get_settings.cache_clear()
    asyncio.run(_create_schema(url))
    yield url
    get_settings.cache_clear()


def test_cli_stores_collected_vacancies(
    cli_database: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """The command saves what it collects — the point of issue #40."""
    assert main(["--limit", "2"]) == 0

    assert asyncio.run(_count_vacancies(cli_database)) == 2
    captured = capsys.readouterr()
    assert "Vacancy 1" in captured.out, "the listing is still printed"
    assert "2 vacancies collected, 2 saved" in captured.err


def test_rerunning_the_cli_stores_nothing_new(
    cli_database: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Idempotent: a second pass over the same listing duplicates nothing."""
    assert main(["--limit", "2"]) == 0
    capsys.readouterr()

    assert main(["--limit", "2"]) == 0

    assert asyncio.run(_count_vacancies(cli_database)) == 2
    assert "2 vacancies collected, 0 saved" in capsys.readouterr().err
