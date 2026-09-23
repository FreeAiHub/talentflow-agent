"""Tests for the storage layer: tables, repository, and the vacancies feed."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.models import Vacancy
from talentflow.storage import (
    count_vacancies,
    create_application,
    decide_application,
    finish_run,
    get_vacancy,
    list_vacancies,
    save_score,
    save_vacancies,
    start_run,
)
from talentflow.storage.repository import (
    _latest_score,  # noqa: PLC2701 - verifying history semantics directly
)
from talentflow.storage.tables import ScoredVacancyRow

MODEL = "test/model"


def _vacancy(vacancy_id: str, *, posted_at: datetime | None = None, **overrides: object) -> Vacancy:
    data: dict[str, object] = {
        "id": vacancy_id,
        "title": f"Vacancy {vacancy_id}",
        "company": "Acme",
        "url": f"https://djinni.co/jobs/{vacancy_id}-vacancy/",
        "source": "djinni",
        "description": "Description",
        "posted_at": posted_at,
    }
    data.update(overrides)
    return Vacancy.model_validate(data)


# --- saving ----------------------------------------------------------------


async def test_save_vacancies_inserts_new_rows(session: AsyncSession) -> None:
    added = await save_vacancies(session, [_vacancy("1"), _vacancy("2")])

    assert added == 2
    assert await count_vacancies(session) == 2


async def test_save_vacancies_is_idempotent(session: AsyncSession) -> None:
    """Re-running the parser must not duplicate rows."""
    await save_vacancies(session, [_vacancy("1"), _vacancy("2")])
    added_again = await save_vacancies(session, [_vacancy("1"), _vacancy("2")])

    assert added_again == 0
    assert await count_vacancies(session) == 2


async def test_save_vacancies_keeps_the_first_version(session: AsyncSession) -> None:
    """A vacancy edited upstream must not silently rewrite our record."""
    await save_vacancies(session, [_vacancy("1", title="Original")])
    await save_vacancies(session, [_vacancy("1", title="Edited upstream")])

    stored = await get_vacancy(session, "1")

    assert stored is not None
    assert stored.title == "Original"


async def test_save_vacancies_handles_empty_input(session: AsyncSession) -> None:
    assert await save_vacancies(session, []) == 0


async def test_save_vacancies_tolerates_duplicates_within_one_batch(
    session: AsyncSession,
) -> None:
    added = await save_vacancies(session, [_vacancy("1"), _vacancy("1")])

    assert added == 1
    assert await count_vacancies(session) == 1


async def test_saved_vacancy_round_trips(session: AsyncSession) -> None:
    posted = datetime(2026, 9, 23, 15, 22, 11, tzinfo=UTC)
    await save_vacancies(session, [_vacancy("42", posted_at=posted)])

    stored = await get_vacancy(session, "42")

    assert stored is not None
    assert stored.id == "42"
    assert stored.company == "Acme"
    assert str(stored.url) == "https://djinni.co/jobs/42-vacancy/"
    assert stored.source == "djinni"
    assert stored.posted_at == posted


# --- scoring ---------------------------------------------------------------


async def test_save_score_attaches_score_to_vacancy(session: AsyncSession) -> None:
    await save_vacancies(session, [_vacancy("1")])
    await save_score(session, "1", score=0.9, reasons=["fits ICP"], model=MODEL)

    stored = await get_vacancy(session, "1")

    assert stored is not None
    assert stored.score == 0.9
    assert stored.reasons == ["fits ICP"]


async def test_rescoring_replaces_the_previous_score(session: AsyncSession) -> None:
    """Same model, new score: one row, updated — not two rows."""
    await save_vacancies(session, [_vacancy("1")])
    await save_score(session, "1", score=0.2, reasons=["first"], model=MODEL)
    await save_score(session, "1", score=0.8, reasons=["second"], model=MODEL)

    stored = await get_vacancy(session, "1")

    assert stored is not None
    assert stored.score == 0.8
    assert stored.reasons == ["second"]


async def test_scores_from_different_models_coexist(session: AsyncSession) -> None:
    """Scores from different models are not comparable, so both are kept."""
    await save_vacancies(session, [_vacancy("1")])
    await save_score(session, "1", score=0.3, reasons=[], model="model-a")
    await save_score(session, "1", score=0.7, reasons=[], model="model-b")

    assert await count_vacancies(session) == 1
    rows = await _all_scores(session)
    assert {row.model for row in rows} == {"model-a", "model-b"}


async def test_unscored_vacancy_has_zero_score_and_no_reasons(session: AsyncSession) -> None:
    await save_vacancies(session, [_vacancy("1")])

    stored = await get_vacancy(session, "1")

    assert stored is not None
    assert stored.score == 0.0
    assert stored.reasons == []


@pytest.mark.parametrize("score", [-0.1, 1.1, 2.0])
async def test_save_score_rejects_out_of_range(session: AsyncSession, score: float) -> None:
    await save_vacancies(session, [_vacancy("1")])

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        await save_score(session, "1", score=score, reasons=[], model=MODEL)


async def test_latest_score_is_the_newest(session: AsyncSession) -> None:
    await save_vacancies(session, [_vacancy("1")])
    await save_score(session, "1", score=0.1, reasons=[], model="old")
    await save_score(session, "1", score=0.6, reasons=[], model="new")

    row = await _latest_score(session, "1")

    assert row is not None
    assert row.model == "new"


async def _all_scores(session: AsyncSession) -> list[ScoredVacancyRow]:
    result = await session.execute(select(ScoredVacancyRow))
    return list(result.scalars().all())


# --- listing ---------------------------------------------------------------


async def test_get_vacancy_returns_none_for_unknown_id(session: AsyncSession) -> None:
    assert await get_vacancy(session, "does-not-exist") is None


async def test_list_vacancies_is_empty_initially(session: AsyncSession) -> None:
    assert await list_vacancies(session) == []


async def test_list_vacancies_orders_newest_posted_first(session: AsyncSession) -> None:
    await save_vacancies(
        session,
        [
            _vacancy("old", posted_at=datetime(2026, 1, 1, tzinfo=UTC)),
            _vacancy("new", posted_at=datetime(2026, 9, 1, tzinfo=UTC)),
            _vacancy("mid", posted_at=datetime(2026, 5, 1, tzinfo=UTC)),
        ],
    )

    listing = await list_vacancies(session)

    assert [v.id for v in listing] == ["new", "mid", "old"]


async def test_list_vacancies_tolerates_missing_posted_at(session: AsyncSession) -> None:
    """A vacancy without a date must not break ordering or vanish."""
    await save_vacancies(
        session,
        [_vacancy("dated", posted_at=datetime(2026, 9, 1, tzinfo=UTC)), _vacancy("undated")],
    )

    listing = await list_vacancies(session)

    assert {v.id for v in listing} == {"dated", "undated"}


async def test_list_vacancies_respects_limit_and_offset(session: AsyncSession) -> None:
    await save_vacancies(
        session,
        [_vacancy(str(n), posted_at=datetime(2026, 9, n, tzinfo=UTC)) for n in range(1, 6)],
    )

    first = await list_vacancies(session, limit=2)
    second = await list_vacancies(session, limit=2, offset=2)

    assert [v.id for v in first] == ["5", "4"]
    assert [v.id for v in second] == ["3", "2"]


async def test_min_score_excludes_unscored_vacancies(session: AsyncSession) -> None:
    """'Not scored yet' is not the same as 'scored zero'."""
    await save_vacancies(session, [_vacancy("scored"), _vacancy("unscored")])
    await save_score(session, "scored", score=0.9, reasons=[], model=MODEL)

    listing = await list_vacancies(session, min_score=0.5)

    assert [v.id for v in listing] == ["scored"]


async def test_min_score_filters_by_threshold(session: AsyncSession) -> None:
    await save_vacancies(session, [_vacancy("high"), _vacancy("low")])
    await save_score(session, "high", score=0.9, reasons=[], model=MODEL)
    await save_score(session, "low", score=0.1, reasons=[], model=MODEL)

    listing = await list_vacancies(session, min_score=0.5)

    assert [v.id for v in listing] == ["high"]


# --- applications ----------------------------------------------------------


async def test_application_starts_pending_and_unapproved(session: AsyncSession) -> None:
    await save_vacancies(session, [_vacancy("1")])

    application = await create_application(session, "1", "Dear hiring manager")

    assert application.status == "pending"
    assert application.approved is False
    assert application.decided_at is None


async def test_approving_an_application_records_the_decision(session: AsyncSession) -> None:
    await save_vacancies(session, [_vacancy("1")])
    application = await create_application(session, "1", "text")

    decided = await decide_application(session, application.id, approved=True)

    assert decided is not None
    assert decided.approved is True
    assert decided.status == "approved"
    assert decided.decided_at is not None


async def test_rejecting_an_application_records_the_decision(session: AsyncSession) -> None:
    await save_vacancies(session, [_vacancy("1")])
    application = await create_application(session, "1", "text")

    decided = await decide_application(session, application.id, approved=False)

    assert decided is not None
    assert decided.approved is False
    assert decided.status == "rejected"


async def test_deciding_an_unknown_application_returns_none(session: AsyncSession) -> None:
    assert await decide_application(session, 9999, approved=True) is None


# --- runs ------------------------------------------------------------------


async def test_run_lifecycle(session: AsyncSession) -> None:
    run = await start_run(session, "parse")

    assert run.status == "running"
    assert run.finished_at is None

    finished = await finish_run(session, run.id, items_processed=15)

    assert finished is not None
    assert finished.status == "ok"
    assert finished.items_processed == 15
    assert finished.finished_at is not None


async def test_run_records_failure(session: AsyncSession) -> None:
    run = await start_run(session, "score")

    finished = await finish_run(session, run.id, status="failed", error="rate limited")

    assert finished is not None
    assert finished.status == "failed"
    assert finished.error == "rate limited"


# --- API -------------------------------------------------------------------


async def test_vacancies_endpoint_is_empty_without_data(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/v1/vacancies")

    assert response.status_code == 200
    assert response.json() == []


async def test_vacancies_endpoint_returns_stored_vacancies(
    api_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await save_vacancies(session, [_vacancy("1")])

    response = await api_client.get("/api/v1/vacancies")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == "1"
    assert body[0]["company"] == "Acme"


async def test_vacancies_endpoint_filters_by_min_score(
    api_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await save_vacancies(session, [_vacancy("high"), _vacancy("low")])
    await save_score(session, "high", score=0.95, reasons=["great fit"], model=MODEL)
    await save_score(session, "low", score=0.05, reasons=[], model=MODEL)

    response = await api_client.get("/api/v1/vacancies", params={"min_score": 0.5})

    body = response.json()
    assert [v["id"] for v in body] == ["high"]
    assert body[0]["score"] == 0.95
    assert body[0]["reasons"] == ["great fit"]


@pytest.mark.parametrize(
    "params",
    [{"min_score": -0.1}, {"min_score": 1.5}, {"limit": 0}, {"limit": 10_000}, {"offset": -1}],
)
async def test_vacancies_endpoint_rejects_bad_query_params(
    api_client: httpx.AsyncClient, params: dict[str, float]
) -> None:
    response = await api_client.get("/api/v1/vacancies", params=params)

    assert response.status_code == 422


async def test_vacancies_endpoint_respects_limit(
    api_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await save_vacancies(session, [_vacancy(str(n)) for n in range(5)])

    response = await api_client.get("/api/v1/vacancies", params={"limit": 2})

    assert len(response.json()) == 2
