"""Domain models validated by Pydantic v2."""

from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class Vacancy(BaseModel):
    id: str
    title: str
    company: str
    url: HttpUrl | None = None
    source: str = "jobspy"
    description: str = ""
    posted_at: datetime | None = None


class ScoredVacancy(Vacancy):
    score: float = Field(default=0.0, ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)


class ApplicationResponse(BaseModel):
    vacancy_id: str
    text: str
    approved: bool = False
