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
    """Approve or reject an application. Returns ``None`` if unknown.

    A draft the grounding check rejected cannot be approved: it was stored only
    so the model's output is not lost, not as a candidate for sending.
    """
    row = await session.get(ApplicationRow, application_id)
    if row is None:
        return None
    if row.status == "grounding_failed" and approved:
        raise ApplicationNotSendable(
            f"application {row.id} failed the grounding check; it cannot be approved"
        )
    row.approved = approved
    row.status = "approved" if approved else "rejected"
    row.decided_at = utcnow()
    await session.commit()
    return row


class ApplicationNotSendable(RuntimeError):
    """Raised when something tries to send an application a human has not approved."""


def assert_sendable(application: ApplicationRow) -> None:
    """Refuse to send anything that is not explicitly approved.

    This is the human-in-the-loop gate. It lives here rather than in the future
    sender so that every caller — API, scheduler, bot — passes through the same
    check instead of each having to remember one.
    """
    if not application.approved or application.status != "approved":
        raise ApplicationNotSendable(
            f"application {application.id} is {application.status!r}; "
            "a human must approve it before it can be sent"
        )


async def get_application(session: AsyncSession, application_id: int) -> ApplicationRow | None:
    """Fetch one application, or ``None``."""
    return await session.get(ApplicationRow, application_id)


async def list_applications(
    session: AsyncSession, *, status: str | None = None, limit: int = 100
) -> list[ApplicationRow]:
    """List applications, newest first, optionally filtered by status."""
    statement = select(ApplicationRow)
    if status is not None:
        statement = statement.where(ApplicationRow.status == status)
    statement = statement.order_by(ApplicationRow.id.desc()).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def create_draft_application(
    session: AsyncSession,
    vacancy_id: str,
    text: str,
    *,
    sendable: bool = True,
    auto_approve: bool = False,
) -> ApplicationRow:
    """Store a generated draft.

    Three outcomes, in priority order:

    - the grounding check failed -> ``grounding_failed``, never approvable
    - ``auto_approve`` -> ``approved``, for pipelines running with
      ``human_in_the_loop`` turned off
    - otherwise -> ``pending``, waiting for a person

    A rejected draft is stored rather than discarded: losing it would hide what
    the model produced, and a separate status keeps it from being approved by
    accident. ``auto_approve`` can never override a failed grounding check.
    """
    if not sendable:
        status = "grounding_failed"
        approved = False
    elif auto_approve:
        status = "approved"
        approved = True
    else:
        status = "pending"
        approved = False

    row = ApplicationRow(
        vacancy_id=vacancy_id,
        text=text,
        approved=approved,
        status=status,
    )
    session.add(row)
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
