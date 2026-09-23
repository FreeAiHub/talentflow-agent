"""Outreach generation with a fact-checking pass.

Two calls per draft: one to write it, one to check it against the source text.
The second call exists because the dangerous failure of LLM outreach is not bad
prose — it is a confident invented fact about the client's company. A letter
that says "you're scaling a Django monolith" to a company that never mentioned
Django is worse than no letter.

Nothing produced here is sent. A draft is stored pending and only a human
decision moves it, which is what ``human_in_the_loop`` means in practice.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from talentflow.config import Settings, get_settings
from talentflow.llm.client import Completer, extract_json
from talentflow.llm.errors import LlmError
from talentflow.llm.prompts import render_prompt
from talentflow.models import Vacancy

logger = logging.getLogger(__name__)

PROMPT_NAME = "response_generator"
GROUNDING_PROMPT_NAME = "grounding_checker"

#: Square brackets mean an unfilled placeholder. The prompt forbids emitting
#: them, so one appearing means the draft is unfinished rather than creative.
_PLACEHOLDER = re.compile(r"\[[^\]]{2,}\]")


class GeneratedResponse(BaseModel):
    """A draft outreach message."""

    response_text: str = Field(min_length=1)
    key_highlights: list[str] = Field(default_factory=list)
    cta: str = ""
    tone: str = "direct"
    word_count: int = 0
    reasoning: str = ""


class GroundingIssue(BaseModel):
    """One claim the source text does not support."""

    claim: str
    why: str


class GroundingReport(BaseModel):
    """The fact-checker's verdict on a draft."""

    verdict: Literal["ok", "review", "reject"] = "review"
    unsupported: list[GroundingIssue] = Field(default_factory=list)
    checked: int = 0
    notes: str = ""

    @property
    def is_sendable(self) -> bool:
        """Only a draft with no fabricated facts may be sent."""
        return self.verdict != "reject"


@dataclass
class DraftOutcome:
    """A generated draft and what was found wrong with it."""

    draft: GeneratedResponse
    grounding: GroundingReport | None
    model: str
    provider: str
    cached: bool = False

    @property
    def is_sendable(self) -> bool:
        return self.grounding is None or self.grounding.is_sendable


def count_words(text: str) -> int:
    """Count words the way a reader would."""
    return len(text.split())


def has_placeholder(text: str) -> bool:
    """Whether the text still contains an unfilled ``[placeholder]``."""
    return bool(_PLACEHOLDER.search(text))


class ResponseGenerator:
    """Writes outreach drafts and checks them for invented facts."""

    def __init__(self, client: Completer, *, settings: Settings | None = None) -> None:
        self.client = client
        self.settings = settings or get_settings()

    # --- writing -----------------------------------------------------------

    def build_prompt(self, vacancy: Vacancy) -> str:
        """Render the generation prompt for one vacancy."""
        return render_prompt(
            PROMPT_NAME,
            sender_profile=self.settings.sender_profile,
            cta=self.settings.cta,
            title=vacancy.title,
            company=vacancy.company or "(не указана)",
            posted_at=str(vacancy.posted_at) if vacancy.posted_at else "(не указана)",
            description=vacancy.description or "(описание отсутствует)",
        )

    async def generate(self, vacancy: Vacancy) -> DraftOutcome:
        """Write a draft, then fact-check it unless checking is disabled."""
        result = await self.client.complete(self.build_prompt(vacancy))
        draft = parse_draft(result.text, vacancy)

        grounding: GroundingReport | None = None
        if self.settings.grounding_check_enabled:
            grounding = await self.check_grounding(draft, vacancy)
            if not grounding.is_sendable and self.settings.grounding_reject_is_fatal:
                logger.warning(
                    "Draft for vacancy %s rejected by the grounding check: %s",
                    vacancy.id,
                    "; ".join(issue.claim for issue in grounding.unsupported[:3]),
                )

        return DraftOutcome(
            draft=draft,
            grounding=grounding,
            model=result.model,
            provider=result.provider,
            cached=result.cached,
        )

    # --- checking ----------------------------------------------------------

    def build_grounding_prompt(self, draft: GeneratedResponse, vacancy: Vacancy) -> str:
        return render_prompt(
            GROUNDING_PROMPT_NAME,
            sender_profile=self.settings.sender_profile,
            description=vacancy.description or "(описание отсутствует)",
            draft=draft.response_text,
        )

    async def check_grounding(self, draft: GeneratedResponse, vacancy: Vacancy) -> GroundingReport:
        """Ask a model to list claims the vacancy text does not support."""
        result = await self.client.complete(self.build_grounding_prompt(draft, vacancy))
        return parse_grounding(result.text, vacancy)


def parse_draft(text: str, vacancy: Vacancy) -> GeneratedResponse:
    """Parse and validate a generation answer.

    ``word_count`` is recomputed rather than trusted: a model that miscounts is
    not wrong in a way worth failing over, but the stored number should be true.
    """
    raw: Any = extract_json(text)
    if not isinstance(raw, dict):
        raise LlmError(
            f"generating for vacancy {vacancy.id}: expected a JSON object, got {type(raw).__name__}"
        )
    try:
        draft = GeneratedResponse.model_validate(raw)
    except ValidationError as exc:
        raise LlmError(f"generating for vacancy {vacancy.id}: unusable answer — {exc}") from exc

    if has_placeholder(draft.response_text):
        raise LlmError(
            f"generating for vacancy {vacancy.id}: draft still contains a placeholder — "
            f"{_PLACEHOLDER.search(draft.response_text).group(0)}"  # type: ignore[union-attr]
        )

    return draft.model_copy(update={"word_count": count_words(draft.response_text)})


def parse_grounding(text: str, vacancy: Vacancy) -> GroundingReport:
    """Parse and validate a fact-checking answer."""
    raw: Any = extract_json(text)
    if not isinstance(raw, dict):
        raise LlmError(
            f"grounding check for vacancy {vacancy.id}: expected a JSON object, "
            f"got {type(raw).__name__}"
        )
    try:
        report = GroundingReport.model_validate(raw)
    except ValidationError as exc:
        raise LlmError(
            f"grounding check for vacancy {vacancy.id}: unusable answer — {exc}"
        ) from exc

    # A verdict of "ok" alongside listed problems is contradictory; the problems
    # are the concrete evidence, so trust them and downgrade the verdict.
    if report.verdict == "ok" and report.unsupported:
        logger.warning(
            "Vacancy %s: checker said 'ok' but listed %d unsupported claims; treating as review",
            vacancy.id,
            len(report.unsupported),
        )
        report = report.model_copy(update={"verdict": "review"})

    return report
