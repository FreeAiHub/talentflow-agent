"""Tests for outreach generation, the grounding check and the review gate.

All offline: a stub client stands in for the model.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.config import Settings
from talentflow.generators import (
    ResponseGenerator,
    count_words,
    has_placeholder,
    parse_draft,
    parse_grounding,
)
from talentflow.llm.client import LlmResult
from talentflow.llm.errors import LlmError
from talentflow.models import Vacancy
from talentflow.storage import (
    ApplicationNotSendable,
    assert_sendable,
    create_application,
    create_draft_application,
    decide_application,
    save_vacancies,
)

DRAFT_TEXT = (
    "Hi — you're moving off a monolith onto Python services and want the "
    "database work done without downtime. That's close to what I do."
)

VALID_DRAFT = {
    "response_text": DRAFT_TEXT,
    "key_highlights": ["Monolith-to-services migration", "No-downtime database cutover"],
    "cta": "Reply with a time",
    "tone": "direct",
    "word_count": 999,
    "reasoning": "Leads with the posting's actual pain.",
}

OK_GROUNDING = {"verdict": "ok", "unsupported": [], "checked": 3, "notes": ""}

REJECT_GROUNDING = {
    "verdict": "reject",
    "unsupported": [{"claim": "scaling a Django monolith", "why": "Django is never mentioned"}],
    "checked": 2,
    "notes": "Invented stack.",
}


class StubClient:
    """Answers with a queue of responses, one per call."""

    def __init__(self, *payloads: Any) -> None:
        self.payloads = list(payloads)
        self.prompts: list[str] = []

    async def complete(self, prompt: str, *, system: str | None = None) -> LlmResult:
        self.prompts.append(prompt)
        payload = self.payloads[min(len(self.prompts) - 1, len(self.payloads) - 1)]
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return LlmResult(text=text, model="stub", provider="stub")


def vacancy(vacancy_id: str = "1", **overrides: Any) -> Vacancy:
    data: dict[str, Any] = {
        "id": vacancy_id,
        "title": "Senior Python Developer",
        "company": "Acme",
        "url": f"https://djinni.co/jobs/{vacancy_id}-x/",
        "source": "djinni",
        "description": "We are moving off a monolith onto Python services.",
    }
    data.update(overrides)
    return Vacancy.model_validate(data)


# --- text helpers ----------------------------------------------------------


def test_count_words_counts_whitespace_separated_tokens() -> None:
    assert count_words("one two  three\nfour") == 4


def test_count_words_is_zero_for_empty_text() -> None:
    assert count_words("") == 0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("no placeholders here", False),
        ("ask [Recruiter] directly", True),
        ("see [ЗАПОЛНИТЬ: проекты]", True),
        ("an [x] is too short to count", False),
        ("array[0] indexing", False),
    ],
)
def test_has_placeholder(text: str, expected: bool) -> None:
    assert has_placeholder(text) is expected


# --- draft parsing ---------------------------------------------------------


def test_parse_draft_accepts_a_valid_answer() -> None:
    draft = parse_draft(json.dumps(VALID_DRAFT), vacancy())

    assert draft.response_text == DRAFT_TEXT
    assert draft.key_highlights


def test_parse_draft_recomputes_word_count() -> None:
    """The stored count must be true, not whatever the model claimed."""
    draft = parse_draft(json.dumps({**VALID_DRAFT, "word_count": 999}), vacancy())

    assert draft.word_count == count_words(DRAFT_TEXT)
    assert draft.word_count != 999


def test_parse_draft_rejects_an_empty_message() -> None:
    with pytest.raises(LlmError, match="unusable answer"):
        parse_draft(json.dumps({**VALID_DRAFT, "response_text": ""}), vacancy())


def test_parse_draft_rejects_an_unfilled_placeholder() -> None:
    """A letter addressed to '[Recruiter]' is unfinished, not creative."""
    answer = {**VALID_DRAFT, "response_text": "Hi [Recruiter], saw your role."}

    with pytest.raises(LlmError, match="placeholder"):
        parse_draft(json.dumps(answer), vacancy())


def test_parse_draft_rejects_a_non_object() -> None:
    with pytest.raises(LlmError, match="expected a JSON object"):
        parse_draft(json.dumps(["nope"]), vacancy())


def test_parse_draft_accepts_fenced_json() -> None:
    text = f"```json\n{json.dumps(VALID_DRAFT)}\n```"

    assert parse_draft(text, vacancy()).response_text == DRAFT_TEXT


# --- grounding parsing -----------------------------------------------------


def test_parse_grounding_accepts_a_clean_verdict() -> None:
    report = parse_grounding(json.dumps(OK_GROUNDING), vacancy())

    assert report.verdict == "ok"
    assert report.is_sendable is True


def test_parse_grounding_reject_is_not_sendable() -> None:
    report = parse_grounding(json.dumps(REJECT_GROUNDING), vacancy())

    assert report.verdict == "reject"
    assert report.is_sendable is False
    assert report.unsupported[0].claim == "scaling a Django monolith"


def test_review_verdict_is_still_sendable() -> None:
    """A minor wording problem is for a human to fix, not a hard block."""
    report = parse_grounding(json.dumps({**OK_GROUNDING, "verdict": "review"}), vacancy())

    assert report.is_sendable is True


def test_contradictory_ok_with_claims_is_downgraded() -> None:
    """'ok' plus a list of problems is self-contradictory; the evidence wins."""
    contradictory = {
        "verdict": "ok",
        "unsupported": [{"claim": "x", "why": "y"}],
        "checked": 1,
    }

    report = parse_grounding(json.dumps(contradictory), vacancy())

    assert report.verdict == "review"


def test_parse_grounding_rejects_an_unknown_verdict() -> None:
    with pytest.raises(LlmError, match="unusable answer"):
        parse_grounding(json.dumps({**OK_GROUNDING, "verdict": "maybe"}), vacancy())


# --- generation ------------------------------------------------------------


async def test_generate_returns_a_draft_and_a_verdict() -> None:
    client = StubClient(VALID_DRAFT, OK_GROUNDING)
    generator = ResponseGenerator(client, settings=Settings())

    outcome = await generator.generate(vacancy())

    assert outcome.draft.response_text == DRAFT_TEXT
    assert outcome.grounding is not None
    assert outcome.is_sendable is True
    assert len(client.prompts) == 2


async def test_generation_prompt_carries_sender_and_cta() -> None:
    client = StubClient(VALID_DRAFT, OK_GROUNDING)
    settings = Settings(sender_profile="ОСОБЫЙ ОТПРАВИТЕЛЬ", cta="СЛОВИТЕ СЛОТ")
    generator = ResponseGenerator(client, settings=settings)

    await generator.generate(vacancy())

    assert "ОСОБЫЙ ОТПРАВИТЕЛЬ" in client.prompts[0]
    assert "СЛОВИТЕ СЛОТ" in client.prompts[0]
    assert "Senior Python Developer" in client.prompts[0]


async def test_grounding_prompt_contains_the_draft() -> None:
    client = StubClient(VALID_DRAFT, OK_GROUNDING)
    generator = ResponseGenerator(client, settings=Settings())

    await generator.generate(vacancy())

    assert DRAFT_TEXT in client.prompts[1]


async def test_fabricated_draft_is_not_sendable() -> None:
    client = StubClient(VALID_DRAFT, REJECT_GROUNDING)
    generator = ResponseGenerator(client, settings=Settings())

    outcome = await generator.generate(vacancy())

    assert outcome.is_sendable is False
    assert outcome.grounding is not None
    assert outcome.grounding.unsupported


async def test_grounding_check_can_be_skipped() -> None:
    """One fewer call per draft, at the cost of unchecked claims."""
    client = StubClient(VALID_DRAFT)
    settings = Settings(grounding_check_enabled=False)
    generator = ResponseGenerator(client, settings=settings)

    outcome = await generator.generate(vacancy())

    assert len(client.prompts) == 1
    assert outcome.grounding is None
    # With no check there is nothing to fail, so the draft passes through.
    assert outcome.is_sendable is True


async def test_missing_description_is_labelled() -> None:
    client = StubClient(VALID_DRAFT, OK_GROUNDING)
    generator = ResponseGenerator(client, settings=Settings())

    await generator.generate(vacancy(description=""))

    assert "(описание отсутствует)" in client.prompts[0]


# --- the human-in-the-loop gate --------------------------------------------


async def test_pending_draft_cannot_be_sent(session: AsyncSession) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_application(session, "1", "text")

    with pytest.raises(ApplicationNotSendable, match="must approve it"):
        assert_sendable(application)


async def test_approved_draft_passes_the_gate(session: AsyncSession) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_application(session, "1", "text")

    decided = await decide_application(session, application.id, approved=True)

    assert decided is not None
    assert_sendable(decided)  # does not raise


async def test_rejected_draft_fails_the_gate(session: AsyncSession) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_application(session, "1", "text")

    decided = await decide_application(session, application.id, approved=False)

    assert decided is not None
    with pytest.raises(ApplicationNotSendable):
        assert_sendable(decided)


async def test_grounding_failed_draft_is_stored_but_not_approvable(
    session: AsyncSession,
) -> None:
    """The model's output is kept for inspection, and can never be sent."""
    await save_vacancies(session, [vacancy("1")])
    application = await create_draft_application(session, "1", "invented facts", sendable=False)

    assert application.status == "grounding_failed"
    with pytest.raises(ApplicationNotSendable, match="grounding check"):
        await decide_application(session, application.id, approved=True)


async def test_grounding_failed_draft_can_still_be_rejected(session: AsyncSession) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_draft_application(session, "1", "invented facts", sendable=False)

    decided = await decide_application(session, application.id, approved=False)

    assert decided is not None
    assert decided.status == "rejected"


async def test_sendable_draft_is_created_pending(session: AsyncSession) -> None:
    await save_vacancies(session, [vacancy("1")])

    application = await create_draft_application(session, "1", "good draft", sendable=True)

    assert application.status == "pending"
    assert application.approved is False


async def test_auto_approve_marks_draft_approved(session: AsyncSession) -> None:
    """The human_in_the_loop=false path, for pipelines that run unattended."""
    await save_vacancies(session, [vacancy("1")])

    application = await create_draft_application(
        session, "1", "good draft", sendable=True, auto_approve=True
    )

    assert application.status == "approved"
    assert application.approved is True
    assert_sendable(application)  # does not raise


async def test_auto_approve_cannot_override_a_failed_grounding_check(
    session: AsyncSession,
) -> None:
    """Turning the human off must not turn off fact-checking."""
    await save_vacancies(session, [vacancy("1")])

    application = await create_draft_application(
        session, "1", "invented facts", sendable=False, auto_approve=True
    )

    assert application.status == "grounding_failed"
    assert application.approved is False
    with pytest.raises(ApplicationNotSendable):
        assert_sendable(application)


# --- API -------------------------------------------------------------------


async def test_approve_endpoint_moves_draft_to_approved(
    api_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_application(session, "1", "draft text")

    response = await api_client.post(f"/api/v1/applications/{application.id}/approve")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["approved"] is True
    assert body["decided_at"] is not None


async def test_reject_endpoint_moves_draft_to_rejected(
    api_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_application(session, "1", "draft text")

    response = await api_client.post(f"/api/v1/applications/{application.id}/reject")

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_approving_an_unknown_application_is_404(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.post("/api/v1/applications/9999/approve")

    assert response.status_code == 404


async def test_approving_a_grounding_failed_draft_is_409(
    api_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_draft_application(session, "1", "invented", sendable=False)

    response = await api_client.post(f"/api/v1/applications/{application.id}/approve")

    assert response.status_code == 409


async def test_applications_can_be_listed_and_filtered(
    api_client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await save_vacancies(session, [vacancy("1")])
    first = await create_application(session, "1", "one")
    await create_application(session, "1", "two")
    await decide_application(session, first.id, approved=True)

    everything = await api_client.get("/api/v1/applications")
    pending = await api_client.get("/api/v1/applications", params={"status": "pending"})

    assert len(everything.json()) == 2
    assert [a["status"] for a in pending.json()] == ["pending"]


async def test_application_list_rejects_an_unknown_status(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/api/v1/applications", params={"status": "nonsense"})

    assert response.status_code == 422
