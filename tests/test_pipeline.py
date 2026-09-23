"""Tests for the pipeline, the scheduler and the stats endpoint.

No network: the parser is replaced and the LLM is either absent or stubbed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.config import Settings
from talentflow.models import Vacancy
from talentflow.pipeline import (
    PipelineResult,
    StageResult,
    run_generate,
    run_parse,
    run_pipeline,
    run_score,
)
from talentflow.scheduler import JOB_ID, build_scheduler, stop_scheduler
from talentflow.storage import save_score, save_vacancies
from talentflow.storage.tables import RunRow

MODEL = "test/model"


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


def settings_with(**overrides: Any) -> Settings:
    """Settings with no LLM keys, so scoring is skipped rather than attempted."""
    base: dict[str, Any] = {
        "openrouter_api_key": None,
        "groq_api_key": None,
        "cerebras_api_key": None,
        "pipeline_parse_limit": 10,
        "pipeline_score_limit": 10,
        "pipeline_generate_limit": 0,
    }
    base.update(overrides)
    return Settings(**base)


def fake_parser(monkeypatch: pytest.MonkeyPatch, vacancies: list[Vacancy]) -> list[int]:
    """Replace DjinniParser with a stub; returns the list of limits it saw."""
    seen: list[int] = []

    class FakeParser:
        def __init__(self, *, limit: int = 50, **_: Any) -> None:
            seen.append(limit)

        async def collect(self) -> list[Vacancy]:
            return vacancies[: seen[-1]]

    monkeypatch.setattr("talentflow.pipeline.DjinniParser", FakeParser)
    return seen


async def runs_recorded(session: AsyncSession) -> list[RunRow]:
    result = await session.execute(select(RunRow).order_by(RunRow.id))
    return list(result.scalars().all())


# --- stage results ---------------------------------------------------------


def test_pipeline_result_ok_when_nothing_failed() -> None:
    result = PipelineResult(
        stages=[StageResult("parse", "ok", 5), StageResult("score", "skipped", error="no key")]
    )

    assert result.ok is True
    assert result.collected == 5


def test_pipeline_result_not_ok_when_a_stage_failed() -> None:
    result = PipelineResult(stages=[StageResult("parse", "failed", error="boom")])

    assert result.ok is False


def test_summary_names_every_stage() -> None:
    result = PipelineResult(
        stages=[StageResult("parse", "ok", 3), StageResult("score", "skipped", error="x")]
    )

    assert result.summary() == "parse=ok(3) | score=skipped"


# --- parse -----------------------------------------------------------------


async def test_parse_stage_stores_vacancies(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_parser(monkeypatch, [vacancy("1"), vacancy("2")])

    stored = await run_parse(session, settings_with(pipeline_parse_limit=2))

    assert stored == 2


async def test_parse_respects_the_configured_limit(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    limits = fake_parser(monkeypatch, [vacancy(str(n)) for n in range(10)])

    stored = await run_parse(session, settings_with(pipeline_parse_limit=3))

    assert stored == 3
    assert limits == [3]


async def test_parse_stage_records_a_run(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_parser(monkeypatch, [vacancy("1")])

    await run_pipeline(session, settings=settings_with())

    runs = await runs_recorded(session)
    assert [r.kind for r in runs] == ["parse", "score"]
    parse_run = runs[0]
    assert parse_run.status == "ok"
    assert parse_run.items_processed == 1
    assert parse_run.finished_at is not None


# --- score -----------------------------------------------------------------


async def test_score_is_skipped_without_an_api_key(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing key is a configuration gap, not a crash."""
    fake_parser(monkeypatch, [vacancy("1")])

    result = await run_pipeline(session, settings=settings_with())

    score_stage = next(s for s in result.stages if s.stage == "score")
    assert score_stage.status == "skipped"
    assert score_stage.error is not None
    assert "no API key" in score_stage.error
    assert result.ok is True


async def test_skipped_score_stage_is_recorded_as_skipped(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_parser(monkeypatch, [vacancy("1")])

    await run_pipeline(session, settings=settings_with())

    runs = await runs_recorded(session)
    score_run = next(r for r in runs if r.kind == "score")
    assert score_run.status == "skipped"
    assert score_run.error


async def test_score_stage_does_nothing_without_candidates(session: AsyncSession) -> None:
    assert await run_score(session, settings_with()) == 0


async def test_already_scored_vacancies_are_not_rescored(session: AsyncSession) -> None:
    """Re-running must not pay twice for the same vacancy."""
    await save_vacancies(session, [vacancy("1")])
    await save_score(session, "1", score=0.9, reasons=["already done"], model=MODEL)

    # No API key is configured, so any attempt to score would raise; returning 0
    # proves the already-scored vacancy was filtered out before the call.
    assert await run_score(session, settings_with()) == 0


# --- generate --------------------------------------------------------------


async def test_generate_is_off_by_default(session: AsyncSession) -> None:
    assert await run_generate(session, settings_with()) == 0


async def test_generate_stage_is_absent_from_the_run_by_default(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_parser(monkeypatch, [vacancy("1")])

    result = await run_pipeline(session, settings=settings_with())

    assert [s.stage for s in result.stages] == ["parse", "score"]


async def test_generate_stage_is_included_when_configured(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no key it skips, but it must at least be attempted and recorded."""
    fake_parser(monkeypatch, [vacancy("1")])
    settings = settings_with(pipeline_generate_limit=2)

    result = await run_pipeline(session, settings=settings)

    assert [s.stage for s in result.stages] == ["parse", "score", "generate"]


# --- idempotency -----------------------------------------------------------


async def test_rerunning_the_pipeline_does_not_duplicate(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_parser(monkeypatch, [vacancy("1"), vacancy("2")])

    first = await run_pipeline(session, settings=settings_with())
    second = await run_pipeline(session, settings=settings_with())

    assert first.collected == 2
    assert second.collected == 0, "the second run must collect nothing new"

    from talentflow.storage import count_vacancies

    assert await count_vacancies(session) == 2


async def test_every_run_is_recorded_even_when_it_did_nothing(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_parser(monkeypatch, [vacancy("1")])

    await run_pipeline(session, settings=settings_with())
    await run_pipeline(session, settings=settings_with())

    runs = await runs_recorded(session)
    assert len(runs) == 4  # two runs, two stages each


# --- failure isolation -----------------------------------------------------


async def test_a_failing_stage_does_not_stop_the_next(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenParser:
        def __init__(self, **_: Any) -> None:
            pass

        async def collect(self) -> list[Vacancy]:
            raise RuntimeError("Djinni is down")

    monkeypatch.setattr("talentflow.pipeline.DjinniParser", BrokenParser)

    result = await run_pipeline(session, settings=settings_with())

    assert result.ok is False
    parse_stage = next(s for s in result.stages if s.stage == "parse")
    assert parse_stage.status == "failed"
    assert "Djinni is down" in (parse_stage.error or "")
    # The score stage still ran and recorded itself.
    assert any(s.stage == "score" for s in result.stages)


async def test_failed_stage_is_recorded_with_its_error(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    class BrokenParser:
        def __init__(self, **_: Any) -> None:
            pass

        async def collect(self) -> list[Vacancy]:
            raise RuntimeError("boom")

    monkeypatch.setattr("talentflow.pipeline.DjinniParser", BrokenParser)

    await run_pipeline(session, settings=settings_with())

    runs = await runs_recorded(session)
    parse_run = next(r for r in runs if r.kind == "parse")
    assert parse_run.status == "failed"
    assert parse_run.error is not None


# --- scheduler -------------------------------------------------------------


def test_scheduler_is_disabled_by_default() -> None:
    """An accidental uvicorn must not start hitting Djinni."""
    assert Settings().scheduler_enabled is False


def test_scheduler_registers_the_pipeline_job() -> None:
    scheduler = build_scheduler(settings_with(scheduler_interval_minutes=15))

    job = scheduler.get_job(JOB_ID)
    assert job is not None
    assert job.max_instances == 1, "a slow run must not overlap the next"
    assert job.coalesce is True, "missed runs must collapse into one"


def test_stopping_when_not_started_is_harmless() -> None:
    stop_scheduler()  # must not raise


# --- stats endpoint --------------------------------------------------------


async def test_stats_is_zeroed_on_an_empty_database(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/v1/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["vacancies_total"] == 0
    assert body["vacancies_scored"] == 0
    assert body["applications_pending"] == 0
    assert body["llm_calls_today"] == 0
    assert body["last_run"] is None
    assert body["scheduler_running"] is False


async def test_stats_counts_vacancies_and_scores(
    api_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await save_vacancies(session, [vacancy("1"), vacancy("2")])
    await save_score(session, "1", score=0.9, reasons=["good"], model=MODEL)
    await save_score(session, "2", score=0.1, reasons=["bad"], model=MODEL)

    body = (await api_client.get("/api/v1/stats")).json()

    assert body["vacancies_total"] == 2
    assert body["vacancies_scored"] == 2
    assert body["vacancies_above_threshold"] == 1


async def test_stats_reports_budget_remaining(api_client: httpx.AsyncClient) -> None:
    body = (await api_client.get("/api/v1/stats")).json()

    assert body["llm_daily_call_limit"] == 500 or body["llm_daily_call_limit"] > 0
    assert body["llm_budget_remaining"] == body["llm_daily_call_limit"]


async def test_stats_shows_the_last_run(
    api_client: httpx.AsyncClient, session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_parser(monkeypatch, [vacancy("1")])
    await run_pipeline(session, settings=settings_with())

    body = (await api_client.get("/api/v1/stats")).json()

    assert body["last_run"] is not None
    assert body["last_run"]["kind"] == "score"
    assert body["last_run"]["status"] == "skipped"


async def test_stats_reports_pending_drafts(
    api_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    from talentflow.storage import create_application, create_draft_application

    await save_vacancies(session, [vacancy("1")])
    await create_application(session, "1", "pending draft")
    await create_draft_application(session, "1", "invented", sendable=False)

    body = (await api_client.get("/api/v1/stats")).json()

    assert body["applications_pending"] == 1
    assert body["applications_grounding_failed"] == 1
