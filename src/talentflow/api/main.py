"""FastAPI application: REST feed + voice/webhook entrypoints."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.models import ScoredVacancy
from talentflow.storage import dispose_engine, get_session
from talentflow.storage import list_vacancies as repository_list_vacancies

DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 500

# Annotated rather than a default value: FastAPI reads it the same way, and the
# dependency stays out of the signature defaults.
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Release pooled database connections on shutdown."""
    yield
    await dispose_engine()


app = FastAPI(title="TalentFlow Agent", version="0.1.0", lifespan=lifespan)


class Health(BaseModel):
    status: str
    version: str


class VapiWebhook(BaseModel):
    event: str
    payload: dict = Field(default_factory=dict)


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


@app.post("/webhooks/vapi")
async def vapi_webhook(event: VapiWebhook) -> dict:
    """Vapi voice webhook; HMAC signature validation lands in phase 2."""
    return {"received": event.event}
