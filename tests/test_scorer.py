"""Tests for vacancy scoring and prompt rendering.

The scorer is exercised with a stub client, so these tests describe scoring
behaviour rather than HTTP behaviour. Provider mechanics live in
``test_llm_client.py``.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from talentflow.config import DEFAULT_ICP_PROFILE, Settings
from talentflow.llm.client import LlmResult
from talentflow.llm.errors import LlmError
from talentflow.llm.prompts import PromptNotFound, load_prompt, render, render_prompt
from talentflow.models import ScoredVacancy, Vacancy
from talentflow.scorers import QualityScorer, parse_payload

VALID_ANSWER = {
    "score": 0.82,
    "reasons": ["Прямой работодатель", "Стек Python совпадает"],
    "signals": {
        "role_level": "senior",
        "is_direct_employer": True,
        "is_agency_resale": False,
        "unpaid_or_equity": False,
        "matched_technologies": ["Python"],
        "location": "remote",
    },
    "unknowns": ["Бюджет не указан"],
    "summary": "Хороший лид.",
}


class StubClient:
    """Stands in for :class:`~talentflow.llm.client.LLMClient`."""

    def __init__(self, payload: Any = None, *, error: Exception | None = None) -> None:
        self.payload = VALID_ANSWER if payload is None else payload
        self.error = error
        self.prompts: list[str] = []

    async def complete(self, prompt: str, *, system: str | None = None) -> LlmResult:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        text = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return LlmResult(text=text, model="stub-model", provider="stub", tokens_in=5, tokens_out=3)


def vacancy(vacancy_id: str = "1", **overrides: Any) -> Vacancy:
    data: dict[str, Any] = {
        "id": vacancy_id,
        "title": "Senior Python Developer",
        "company": "Acme",
        "url": f"https://djinni.co/jobs/{vacancy_id}-x/",
        "source": "djinni",
        "description": "Build APIs with FastAPI.",
    }
    data.update(overrides)
    return Vacancy.model_validate(data)


# --- prompt rendering ------------------------------------------------------


def test_render_replaces_known_placeholders() -> None:
    assert render("Hello {name}!", name="world") == "Hello world!"


def test_render_leaves_json_braces_alone() -> None:
    """The prompt embeds JSON examples; str.format would choke on them."""
    template = 'Return {"score": 0.5} for {title}'

    assert render(template, title="X") == 'Return {"score": 0.5} for X'


def test_render_raises_on_unknown_placeholder() -> None:
    """A typo in a placeholder must fail loudly, not ship a literal brace."""
    with pytest.raises(KeyError, match="missing"):
        render("Hello {missing}!", name="world")


def test_render_tolerates_a_template_without_placeholders() -> None:
    assert render("plain text") == "plain text"


def test_scorer_prompt_loads() -> None:
    assert "Scoring rubric" in load_prompt("vacancy_scorer")


def test_missing_prompt_raises_a_useful_error() -> None:
    with pytest.raises(PromptNotFound, match="TALENTFLOW_PROMPTS_DIR"):
        load_prompt("no_such_prompt")


def test_rendered_scorer_prompt_contains_the_vacancy() -> None:
    prompt = render_prompt(
        "vacancy_scorer",
        icp_profile="ICP TEXT",
        title="Backend Engineer",
        company="Globex",
        source="djinni",
        posted_at="2026-09-23",
        description="DESCRIPTION TEXT",
    )

    assert "ICP TEXT" in prompt
    assert "Backend Engineer" in prompt
    assert "Globex" in prompt
    assert "DESCRIPTION TEXT" in prompt
    # The JSON example must survive rendering intact.
    assert '"score"' in prompt


# --- payload validation ----------------------------------------------------


def test_parse_payload_accepts_a_valid_answer() -> None:
    payload = parse_payload(json.dumps(VALID_ANSWER), vacancy())

    assert payload.score == 0.82
    assert payload.reasons == VALID_ANSWER["reasons"]
    assert payload.signals.role_level == "senior"


@pytest.mark.parametrize("bad_score", [-0.1, 1.5, 7, 100])
def test_parse_payload_rejects_out_of_range_scores(bad_score: float) -> None:
    """A model answering on a 0-10 scale must fail, not be silently clamped."""
    answer = {**VALID_ANSWER, "score": bad_score}

    with pytest.raises(LlmError, match="unusable answer"):
        parse_payload(json.dumps(answer), vacancy())


def test_parse_payload_rejects_empty_reasons() -> None:
    answer = {**VALID_ANSWER, "reasons": []}

    with pytest.raises(LlmError, match="unusable answer"):
        parse_payload(json.dumps(answer), vacancy())


def test_parse_payload_rejects_a_missing_score() -> None:
    answer = {k: v for k, v in VALID_ANSWER.items() if k != "score"}

    with pytest.raises(LlmError, match="unusable answer"):
        parse_payload(json.dumps(answer), vacancy())


def test_parse_payload_rejects_a_non_object() -> None:
    with pytest.raises(LlmError, match="expected a JSON object"):
        parse_payload(json.dumps([1, 2, 3]), vacancy())


def test_parse_payload_defaults_optional_fields() -> None:
    """`signals`, `unknowns` and `summary` are nice-to-have, not required."""
    payload = parse_payload(json.dumps({"score": 0.5, "reasons": ["ok"]}), vacancy())

    assert payload.score == 0.5
    assert payload.signals.role_level == "unknown"
    assert payload.unknowns == []
    assert payload.summary == ""


def test_parse_payload_accepts_fenced_json() -> None:
    text = f"```json\n{json.dumps(VALID_ANSWER)}\n```"

    assert parse_payload(text, vacancy()).score == 0.82


# --- scoring ---------------------------------------------------------------


async def test_score_returns_a_scored_vacancy() -> None:
    scorer = QualityScorer(StubClient(), settings=Settings())

    outcome = await scorer.score(vacancy())

    assert outcome.score == 0.82
    assert outcome.vacancy.reasons == VALID_ANSWER["reasons"]
    assert outcome.model == "stub-model"
    assert outcome.tokens_in == 5


async def test_score_preserves_the_original_vacancy_fields() -> None:
    scorer = QualityScorer(StubClient(), settings=Settings())

    outcome = await scorer.score(vacancy("42", company="Globex", title="QA Lead"))

    assert outcome.vacancy.id == "42"
    assert outcome.vacancy.company == "Globex"
    assert outcome.vacancy.title == "QA Lead"
    assert outcome.vacancy.source == "djinni"


async def test_score_accepts_an_already_scored_vacancy() -> None:
    """The scorer is fed ``ScoredVacancy`` rows, not bare ``Vacancy`` ones.

    ``list_vacancies`` returns scored rows so callers can tell "not scored yet"
    from "scored badly". Regression: the result was built with
    ``**vacancy.model_dump()``, which already carried ``score``, so the live
    pipeline died with ``TypeError: got multiple values for keyword argument
    'score'`` while every test that passed a plain ``Vacancy`` stayed green.
    """
    scorer = QualityScorer(StubClient(), settings=Settings())
    stored = ScoredVacancy(**vacancy("42").model_dump(), score=0.0, reasons=[])

    outcome = await scorer.score(stored)

    assert outcome.score == 0.82
    assert outcome.vacancy.id == "42"
    assert outcome.vacancy.reasons == VALID_ANSWER["reasons"]


async def test_score_overwrites_a_stale_score_from_the_database() -> None:
    """A previous score on the row must not leak into the new outcome."""
    scorer = QualityScorer(StubClient(), settings=Settings())
    stored = ScoredVacancy(**vacancy("7").model_dump(), score=0.1, reasons=["старое"])

    outcome = await scorer.score(stored)

    assert outcome.score == 0.82
    assert outcome.vacancy.reasons == VALID_ANSWER["reasons"]


async def test_score_raises_when_the_model_is_unusable() -> None:
    """A vacancy is never silently scored zero."""
    scorer = QualityScorer(StubClient(error=LlmError("provider down")), settings=Settings())

    with pytest.raises(LlmError, match="provider down"):
        await scorer.score(vacancy())


async def test_prompt_includes_the_configured_icp() -> None:
    client = StubClient()
    settings = Settings(icp_profile="ОСОБЫЙ ICP")
    scorer = QualityScorer(client, settings=settings)

    await scorer.score(vacancy())

    assert "ОСОБЫЙ ICP" in client.prompts[0]


def test_default_settings_carry_an_icp() -> None:
    """The shipped ICP is a placeholder, but it must not be empty."""
    assert Settings().icp_profile == DEFAULT_ICP_PROFILE
    assert len(DEFAULT_ICP_PROFILE) > 40


async def test_missing_description_is_labelled_not_blank() -> None:
    client = StubClient()
    scorer = QualityScorer(client, settings=Settings())

    await scorer.score(vacancy(description=""))

    assert "(описание отсутствует)" in client.prompts[0]


# --- batch scoring ---------------------------------------------------------


async def test_score_many_returns_every_outcome() -> None:
    scorer = QualityScorer(StubClient(), settings=Settings())

    outcomes = await scorer.score_many([vacancy("1"), vacancy("2")])

    assert len(outcomes) == 2
    assert {o.vacancy.id for o in outcomes} == {"1", "2"}


async def test_score_many_skips_unusable_vacancies_without_stopping() -> None:
    """One bad answer must not abandon the batch."""
    scorer = QualityScorer(
        StubClient(payload={"score": 5, "reasons": ["bad"]}), settings=Settings()
    )

    with pytest.raises(LlmError):
        # Every vacancy fails, so the batch reports failure rather than
        # pretending it scored nothing successfully.
        await scorer.score_many([vacancy("1"), vacancy("2")])


async def test_score_many_partial_failure_keeps_the_good_ones() -> None:
    class FlakyClient(StubClient):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        async def complete(self, prompt: str, *, system: str | None = None) -> LlmResult:
            self.calls += 1
            if self.calls == 1:
                raise LlmError("first one fails")
            return await super().complete(prompt, system=system)

    scorer = QualityScorer(FlakyClient(), settings=Settings())

    outcomes = await scorer.score_many([vacancy("1"), vacancy("2")])

    assert len(outcomes) == 1
    assert outcomes[0].vacancy.id == "2"


# --- threshold -------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "expected"),
    [(0.9, True), (0.6, True), (0.59, False), (0.0, False)],
)
async def test_is_worth_pursuing_uses_the_threshold(score: float, expected: bool) -> None:
    scorer = QualityScorer(
        StubClient(payload={**VALID_ANSWER, "score": score}), settings=Settings()
    )

    outcome = await scorer.score(vacancy())

    assert scorer.is_worth_pursuing(outcome.vacancy) is expected
