"""Vacancy lead scoring.

Turns a collected vacancy into a relevance score with reasons, using the prompt
in ``prompts/vacancy_scorer.md``.

The response is validated into a Pydantic schema rather than trusted: models
asked for JSON occasionally return a number out of range, a missing field, or
prose with braces in it. Each of those becomes a clear error naming the vacancy,
not a silent zero.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from talentflow.config import Settings, get_settings
from talentflow.llm.client import Completer, extract_json
from talentflow.llm.errors import LlmBudgetExceeded, LlmError, NoProviderConfigured
from talentflow.llm.prompts import render_prompt
from talentflow.models import ScoredVacancy, Vacancy

logger = logging.getLogger(__name__)

PROMPT_NAME = "vacancy_scorer"

#: Scores below this are treated as "not worth pursuing" by default.
DEFAULT_MIN_SCORE = 0.6

#: The prompt asks for at least this many reasons; fewer is a quality signal
#: worth logging, though not a hard failure.
MIN_EXPECTED_REASONS = 2


class ScoringSignals(BaseModel):
    """Structured flags the model reports alongside the score."""

    role_level: str = "unknown"
    is_direct_employer: bool = False
    is_agency_resale: bool = False
    unpaid_or_equity: bool = False
    matched_technologies: list[str] = Field(default_factory=list)
    location: str = "unknown"


class ScoringPayload(BaseModel):
    """The model's answer, validated.

    ``score`` is bounded and ``reasons`` may not be empty — the two properties
    the rest of the pipeline relies on.
    """

    score: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(min_length=1)
    signals: ScoringSignals = Field(default_factory=ScoringSignals)
    unknowns: list[str] = Field(default_factory=list)
    summary: str = ""


@dataclass
class ScoreOutcome:
    """A scored vacancy and the provenance of the score."""

    vacancy: ScoredVacancy
    model: str
    provider: str
    cached: bool = False
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def score(self) -> float:
        return self.vacancy.score


class QualityScorer:
    """Scores vacancies against the configured ideal-customer profile."""

    def __init__(
        self,
        client: Completer,
        *,
        min_score: float = DEFAULT_MIN_SCORE,
        settings: Settings | None = None,
    ) -> None:
        self.client = client
        self.min_score = min_score
        self.settings = settings or get_settings()

    def build_prompt(self, vacancy: Vacancy) -> str:
        """Render the scoring prompt for one vacancy."""
        return render_prompt(
            PROMPT_NAME,
            icp_profile=self.settings.icp_profile,
            title=vacancy.title,
            company=vacancy.company or "(не указана)",
            source=vacancy.source,
            posted_at=str(vacancy.posted_at) if vacancy.posted_at else "(не указана)",
            description=vacancy.description or "(описание отсутствует)",
        )

    async def score(self, vacancy: Vacancy) -> ScoreOutcome:
        """Score one vacancy.

        Raises :class:`~talentflow.llm.errors.LlmError` when the model cannot be
        reached or answers unusably — a vacancy is never silently scored zero.
        """
        result = await self.client.complete(self.build_prompt(vacancy))
        payload = parse_payload(result.text, vacancy)

        if len(payload.reasons) < MIN_EXPECTED_REASONS:
            logger.warning(
                "Vacancy %s got only %d reason(s); the prompt asks for %d",
                vacancy.id,
                len(payload.reasons),
                MIN_EXPECTED_REASONS,
            )

        scored = ScoredVacancy(
            **vacancy.model_dump(),
            score=payload.score,
            reasons=payload.reasons,
        )
        return ScoreOutcome(
            vacancy=scored,
            model=result.model,
            provider=result.provider,
            cached=result.cached,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
        )

    async def score_many(self, vacancies: Sequence[Vacancy]) -> list[ScoreOutcome]:
        """Score several vacancies, skipping the ones that cannot be scored.

        One unusable answer must not abandon the batch. A missing key or an
        exhausted budget, however, is not a per-vacancy problem: those stop the
        batch at once and keep their own exception type, so the caller can tell
        "nothing to spend" from "provider is broken".
        """
        outcomes: list[ScoreOutcome] = []
        errors: list[LlmError] = []

        for vacancy in vacancies:
            try:
                outcomes.append(await self.score(vacancy))
            except (LlmBudgetExceeded, NoProviderConfigured):
                # Not a per-vacancy problem: every remaining one fails the same
                # way, so stop rather than repeating the same error N times.
                raise
            except LlmError as exc:
                errors.append(exc)
                logger.warning("Skipping vacancy %s: %s", vacancy.id, exc)

        if errors and not outcomes:
            # Re-raise as the original type: the pipeline separates "nothing to
            # spend" from "provider is down", and a bare LlmError erases that.
            first = errors[0]
            detail = "; ".join(str(e) for e in errors[:5])
            raise type(first)(f"no vacancy could be scored — {detail}") from first
        if errors:
            logger.warning("%d of %d vacancies failed to score", len(errors), len(vacancies))

        return outcomes

    def is_worth_pursuing(self, scored: ScoredVacancy) -> bool:
        """Whether a score clears the configured threshold."""
        return scored.score >= self.min_score


def parse_payload(text: str, vacancy: Vacancy) -> ScoringPayload:
    """Parse and validate a model answer for one vacancy."""
    raw: Any = extract_json(text)
    if not isinstance(raw, dict):
        raise LlmError(
            f"scoring vacancy {vacancy.id}: expected a JSON object, got {type(raw).__name__}"
        )
    try:
        return ScoringPayload.model_validate(raw)
    except ValidationError as exc:
        raise LlmError(f"scoring vacancy {vacancy.id}: unusable answer — {exc}") from exc
