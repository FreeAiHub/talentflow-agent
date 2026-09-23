"""FastAPI application: REST feed, application review, voice/webhook entrypoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.config import get_settings
from talentflow.models import ScoredVacancy
from talentflow.scheduler import get_scheduler, start_scheduler, stop_scheduler
from talentflow.storage import (
    ApplicationNotSendable,
    collect_stats,
    decide_application,
    dispose_engine,
    get_application,
    get_session,
    list_applications,
)
from talentflow.storage import list_vacancies as repository_list_vacancies

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

# Annotated rather than a default value: FastAPI reads it the same way, and the
# dependency stays out of the signature defaults.
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Start the scheduler on boot, release everything on shutdown.

    The scheduler only starts when ``TALENTFLOW_SCHEDULER_ENABLED`` is true, so
    a development server does not quietly begin collecting and spending.
    """
    start_scheduler(get_settings())
    try:
        yield
    finally:
        stop_scheduler()
        await dispose_engine()


app = FastAPI(title="TalentFlow Agent", version="0.1.0", lifespan=lifespan)


class Health(BaseModel):
    status: str
    version: str


class VapiWebhook(BaseModel):
    event: str
    payload: dict = Field(default_factory=dict)


class ApplicationOut(BaseModel):
    """A generated draft and its review state."""

    id: int
    vacancy_id: str
    text: str
    approved: bool
    status: Literal["pending", "approved", "rejected", "grounding_failed"]
    created_at: datetime
    decided_at: datetime | None = None


class RunOut(BaseModel):
    """One recorded pipeline stage."""

    id: int
    kind: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    items_processed: int
    error: str | None = None


class StatsOut(BaseModel):
    """A snapshot of the pipeline."""

    vacancies_total: int
    vacancies_scored: int
    vacancies_above_threshold: int
    applications_pending: int
    applications_approved: int
    applications_grounding_failed: int
    #: Calls are counted from the ``llm_calls`` table, so failures count too.
    llm_calls_today: int
    llm_failures_today: int
    llm_daily_call_limit: int
    llm_budget_remaining: int
    min_lead_score: float
    #: False means the pipeline only runs when invoked by hand.
    scheduler_running: bool
    last_run: RunOut | None = None


@app.get("/health", response_model=Health)
async def health() -> Health:
    return Health(status="ok", version=app.version)


@app.get("/api/v1/vacancies", response_model=list[ScoredVacancy])
async def list_vacancies(
    session: SessionDep,
    min_score: Annotated[
        float | None,
        Query(
            ge=0.0,
            le=1.0,
            description="Only vacancies scored at or above this value. "
            "Unscored vacancies are excluded rather than treated as zero.",
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ScoredVacancy]:
    """Scored vacancies, newest first."""
    return await repository_list_vacancies(session, min_score=min_score, limit=limit, offset=offset)


@app.get("/api/v1/applications", response_model=list[ApplicationOut])
async def list_application_drafts(
    session: SessionDep,
    application_status: Annotated[
        Literal["pending", "approved", "rejected", "grounding_failed"] | None,
        Query(alias="status", description="Filter by review state."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> list[ApplicationOut]:
    """Outreach drafts awaiting or following review, newest first."""
    rows = await list_applications(session, status=application_status, limit=limit)
    return [ApplicationOut.model_validate(row, from_attributes=True) for row in rows]


@app.post("/api/v1/applications/{application_id}/approve", response_model=ApplicationOut)
async def approve_application(application_id: int, session: SessionDep) -> ApplicationOut:
    """Approve a draft for sending.

    Until this is called the draft stays pending, and the send gate refuses it.
    """
    return await _decide(session, application_id, approved=True)


@app.post("/api/v1/applications/{application_id}/reject", response_model=ApplicationOut)
async def reject_application(application_id: int, session: SessionDep) -> ApplicationOut:
    """Reject a draft so it is never sent."""
    return await _decide(session, application_id, approved=False)


async def _decide(session: AsyncSession, application_id: int, *, approved: bool) -> ApplicationOut:
    existing = await get_application(session, application_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"application {application_id} not found",
        )
    try:
        row = await decide_application(session, application_id, approved=approved)
    except ApplicationNotSendable as exc:
        # 409: the request is well-formed, the resource is in the wrong state.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    assert row is not None  # existence was checked above
    return ApplicationOut.model_validate(row, from_attributes=True)


@app.get("/api/v1/stats", response_model=StatsOut)
async def stats(session: SessionDep) -> StatsOut:
    """What the pipeline has done: totals, review queue, and today's LLM spend."""
    settings = get_settings()
    collected = await collect_stats(session, min_score=settings.min_lead_score)
    scheduler = get_scheduler()

    return StatsOut(
        vacancies_total=collected.vacancies_total,
        vacancies_scored=collected.vacancies_scored,
        vacancies_above_threshold=collected.vacancies_above_threshold,
        applications_pending=collected.applications_pending,
        applications_approved=collected.applications_approved,
        applications_grounding_failed=collected.applications_grounding_failed,
        llm_calls_today=collected.llm_calls_today,
        llm_failures_today=collected.llm_failures_today,
        llm_daily_call_limit=settings.llm_daily_call_limit,
        llm_budget_remaining=max(0, settings.llm_daily_call_limit - collected.llm_calls_today),
        min_lead_score=settings.min_lead_score,
        scheduler_running=scheduler is not None,
        last_run=(
            RunOut.model_validate(collected.last_run, from_attributes=True)
            if collected.last_run
            else None
        ),
    )


@app.post("/webhooks/vapi")
async def vapi_webhook(event: VapiWebhook) -> dict:
    """Vapi voice webhook; HMAC signature validation lands in phase 2."""
    return {"received": event.event}
