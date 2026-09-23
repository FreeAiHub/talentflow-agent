"""Repository layer: the only place that knows about both rows and domain models.

Callers work with :class:`~talentflow.models.Vacancy` and
:class:`~talentflow.models.ScoredVacancy`; nothing outside this module imports
:mod:`talentflow.storage.tables`.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.models import ScoredVacancy, Vacancy
from talentflow.storage.tables import (
    ApplicationRow,
    RunRow,
    ScoredVacancyRow,
    VacancyRow,
    utcnow,
)


def _to_domain(row: VacancyRow, score: ScoredVacancyRow | None = None) -> ScoredVacancy:
    """Build a domain model from a vacancy row and, optionally, its score."""
    return ScoredVacancy.model_validate(
        {
            "id": row.id,
            "title": row.title,
            "company": row.company,
            "url": row.url,
            "source": row.source,
            "description": row.description,
            "posted_at": row.posted_at,
            "score": score.score if score else 0.0,
            "reasons": list(score.reasons or []) if score else [],
        }
    )


async def save_vacancies(session: AsyncSession, vacancies: Sequence[Vacancy]) -> int:
    """Insert vacancies that are not stored yet; return how many were added.

    Idempotent by source id, so re-running the parser is harmless. Existing rows
    are left untouched: the first version we saw is the one we keep, and a
    description edited upstream does not silently rewrite our record.
    """
    if not vacancies:
        return 0

    incoming = {v.id: v for v in vacancies}
    result = await session.execute(select(VacancyRow.id).where(VacancyRow.id.in_(incoming)))
    known = set(result.scalars().all())

    added = 0
    for vacancy_id, vacancy in incoming.items():
        if vacancy_id in known:
            continue
        session.add(
            VacancyRow(
                id=vacancy.id,
                source=vacancy.source,
                title=vacancy.title,
                company=vacancy.company,
                url=str(vacancy.url) if vacancy.url else None,
                description=vacancy.description,
                posted_at=vacancy.posted_at,
            )
        )
        added += 1

    await session.commit()
    return added


async def count_vacancies(session: AsyncSession) -> int:
    """Number of stored vacancies."""
    result = await session.execute(select(func.count()).select_from(VacancyRow))
    return int(result.scalar_one())


async def get_vacancy(session: AsyncSession, vacancy_id: str) -> ScoredVacancy | None:
    """Fetch one vacancy with its latest score, or ``None``."""
    row = await session.get(VacancyRow, vacancy_id)
    if row is None:
        return None
    score = await _latest_score(session, vacancy_id)
    return _to_domain(row, score)


async def list_vacancies(
    session: AsyncSession,
    *,
    min_score: float | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[ScoredVacancy]:
    """Return vacancies, newest first, optionally filtered by score.

    When ``min_score`` is given, only vacancies that have been scored at or
    above it are returned — unscored vacancies are excluded rather than treated
    as zero, because "not scored yet" and "scored badly" are different things.
    """
    statement = select(VacancyRow, ScoredVacancyRow).outerjoin(
        ScoredVacancyRow, ScoredVacancyRow.vacancy_id == VacancyRow.id
    )
    if min_score is not None:
        statement = statement.where(ScoredVacancyRow.score >= min_score)

    statement = (
        statement.order_by(VacancyRow.posted_at.desc().nullslast(), VacancyRow.id.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await session.execute(statement)
    return [_to_domain(row, score) for row, score in result.all()]


async def save_score(
    session: AsyncSession,
    vacancy_id: str,
    *,
    score: float,
    reasons: Sequence[str],
    model: str,
) -> ScoredVacancyRow:
    """Store a score, replacing any previous score from the same model.

    Scores from different models coexist: they are not comparable, and keeping
    both is what makes a model switch auditable.
    """
    if not 0.0 <= score <= 1.0:
        raise ValueError(f"score must be within [0, 1], got {score!r}")

    result = await session.execute(
        select(ScoredVacancyRow).where(
            ScoredVacancyRow.vacancy_id == vacancy_id,
            ScoredVacancyRow.model == model,
        )
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = ScoredVacancyRow(
            vacancy_id=vacancy_id,
            score=score,
            reasons=list(reasons),
            model=model,
        )
        session.add(row)
    else:
        row.score = score
        row.reasons = list(reasons)
        row.scored_at = utcnow()

    await session.commit()
    return row


async def _latest_score(session: AsyncSession, vacancy_id: str) -> ScoredVacancyRow | None:
    result = await session.execute(
        select(ScoredVacancyRow)
        .where(ScoredVacancyRow.vacancy_id == vacancy_id)
        .order_by(ScoredVacancyRow.scored_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def create_application(session: AsyncSession, vacancy_id: str, text: str) -> ApplicationRow:
    """Create a pending application. Nothing is sent until it is approved."""
    row = ApplicationRow(vacancy_id=vacancy_id, text=text, approved=False, status="pending")
    session.add(row)
    await session.commit()
    return row


async def decide_application(
    session: AsyncSession, application_id: int, *, approved: bool
) -> ApplicationRow | None:
    """Approve or reject a pending application. Returns ``None`` if unknown."""
    row = await session.get(ApplicationRow, application_id)
    if row is None:
        return None
    row.approved = approved
    row.status = "approved" if approved else "rejected"
    row.decided_at = utcnow()
    await session.commit()
    return row


async def start_run(session: AsyncSession, kind: str) -> RunRow:
    """Record the start of a pipeline run."""
    row = RunRow(kind=kind, status="running")
    session.add(row)
    await session.commit()
    return row


async def finish_run(
    session: AsyncSession,
    run_id: int,
    *,
    status: str = "ok",
    items_processed: int = 0,
    error: str | None = None,
) -> RunRow | None:
    """Record the outcome of a pipeline run."""
    row = await session.get(RunRow, run_id)
    if row is None:
        return None
    row.status = status
    row.items_processed = items_processed
    row.error = error
    row.finished_at = utcnow()
    await session.commit()
    return row
