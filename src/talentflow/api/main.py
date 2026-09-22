"""FastAPI application: REST feed + voice/webhook entrypoints."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from talentflow.models import ScoredVacancy

app = FastAPI(title="TalentFlow Agent", version="0.1.0")


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
async def list_vacancies() -> list[ScoredVacancy]:
    """Scored vacancies feed (backed by parser + scorer on MVP Day 2)."""
    return []


@app.post("/webhooks/vapi")
async def vapi_webhook(event: VapiWebhook) -> dict:
    """Vapi voice webhook; HMAC signature validation lands in phase 2."""
    return {"received": event.event}
