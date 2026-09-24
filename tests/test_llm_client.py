"""Tests for the LLM client: provider chain, budget, cache and JSON handling.

Every test runs against a mock transport — no network, no API key, no cost.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.config import Settings
from talentflow.llm import (
    BudgetGuard,
    LlmBudgetExceeded,
    LLMClient,
    LlmError,
    LlmResponseInvalid,
    ModelRef,
    NoProviderConfigured,
    ResponseCache,
    extract_json,
)
from talentflow.storage.tables import LlmCallRow

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

Handler = Callable[[httpx.Request], httpx.Response]


def settings_with(**overrides: Any) -> Settings:
    """Settings with both providers keyed and a two-model chain."""
    base: dict[str, Any] = {
        "openrouter_api_key": "test-openrouter-key",
        "groq_api_key": "test-groq-key",
        "llm_models": "openrouter:model-a",
        "llm_fallback_models": "groq:model-b",
        "llm_max_attempts": 3,
    }
    base.update(overrides)
    return Settings(**base)


def completion(content: str, *, prompt_tokens: int = 11, completion_tokens: int = 7) -> dict:
    """A minimal OpenAI-compatible chat-completions body."""
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


def json_completion(payload: dict) -> dict:
    return completion(json.dumps(payload))


def client_for(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def calls_recorded(session: AsyncSession) -> list[LlmCallRow]:
    result = await session.execute(select(LlmCallRow).order_by(LlmCallRow.id))
    return list(result.scalars().all())


# --- model reference parsing ----------------------------------------------


def test_model_ref_splits_on_first_colon_only() -> None:
    """OpenRouter model ids contain colons; only the provider prefix is a separator."""
    ref = ModelRef.parse("openrouter:openai/gpt-oss-120b:free")

    assert ref.provider == "openrouter"
    assert ref.model == "openai/gpt-oss-120b:free"


@pytest.mark.parametrize("raw", ["no-colon", ":model", "provider:", ""])
def test_model_ref_rejects_malformed(raw: str) -> None:
    with pytest.raises(ValueError, match="provider:model"):
        ModelRef.parse(raw)


def test_model_chain_lists_primary_then_fallbacks() -> None:
    settings = settings_with(llm_fallback_models="groq:model-b,cerebras:model-c")

    assert [r.model for r in [ModelRef.parse(m) for m in settings.model_chain]] == [
        "model-a",
        "model-b",
        "model-c",
    ]


def test_model_chain_ignores_blank_entries() -> None:
    settings = settings_with(llm_models="openrouter:model-a,", llm_fallback_models=" , ")

    assert settings.model_chain == ["openrouter:model-a"]


# --- JSON extraction -------------------------------------------------------


def test_extract_json_plain() -> None:
    assert extract_json('{"score": 0.5}') == {"score": 0.5}


def test_extract_json_from_fenced_block() -> None:
    """Models fence JSON despite being told not to."""
    assert extract_json('```json\n{"score": 0.5}\n```') == {"score": 0.5}


def test_extract_json_from_unlabelled_fence() -> None:
    assert extract_json('```\n{"score": 0.5}\n```') == {"score": 0.5}


def test_extract_json_after_preamble() -> None:
    assert extract_json('Here is the result:\n{"score": 0.5}') == {"score": 0.5}


@pytest.mark.parametrize("bad", ["", "not json at all", "```json\n{broken\n```", "[1, 2"])
def test_extract_json_raises_on_garbage(bad: str) -> None:
    """Raising beats returning None: a caller treating None as 0 would score everything zero."""
    with pytest.raises(LlmResponseInvalid):
        extract_json(bad)


# --- provider chain --------------------------------------------------------


async def test_completion_returns_text_and_usage(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=completion("hello"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        result = await client.complete("hi")

    assert result.text == "hello"
    assert result.model == "model-a"
    assert result.provider == "openrouter"
    assert result.tokens_in == 11
    assert result.tokens_out == 7
    assert result.cached is False


async def test_every_call_is_recorded(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=completion("ok"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http, purpose="score")
        await client.complete("hi")

    rows = await calls_recorded(session)
    assert len(rows) == 1
    assert rows[0].model == "model-a"
    assert rows[0].provider == "openrouter"
    assert rows[0].purpose == "score"
    assert rows[0].ok is True
    assert rows[0].tokens_in == 11


async def test_falls_back_to_the_second_provider(session: AsyncSession) -> None:
    """A 500 from the primary must not fail the request."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if str(request.url) == OPENROUTER_URL:
            return httpx.Response(500, text="upstream exploded")
        return httpx.Response(200, json=completion("from groq"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        result = await client.complete("hi")

    assert result.text == "from groq"
    assert result.provider == "groq"
    assert result.model == "model-b"
    assert GROQ_URL in seen


async def test_rate_limit_moves_to_the_next_provider_without_retrying(
    session: AsyncSession,
) -> None:
    """429 means slow down: retrying the same provider is how an IP gets banned."""
    attempts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(str(request.url))
        if str(request.url) == OPENROUTER_URL:
            return httpx.Response(429, text="slow down")
        return httpx.Response(200, json=completion("from groq"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        result = await client.complete("hi")

    assert result.provider == "groq"
    assert attempts.count(OPENROUTER_URL) == 1


async def test_provider_without_a_key_is_skipped(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=completion("from groq"))

    settings = settings_with(groq_api_key="test-groq-key")
    settings.openrouter_api_key = None

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings, client=http)
        result = await client.complete("hi")

    assert result.provider == "groq"


async def test_no_configured_provider_raises(session: AsyncSession) -> None:
    """A missing key is a configuration error, not an empty result."""
    settings = Settings(
        openrouter_api_key=None,
        groq_api_key=None,
        cerebras_api_key=None,
        llm_models="openrouter:model-a",
    )

    client = LLMClient(session, settings=settings)
    with pytest.raises(NoProviderConfigured, match="no API key"):
        await client.complete("hi")


async def test_all_providers_failing_raises(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="nope")

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        with pytest.raises(LlmError, match="every provider failed"):
            await client.complete("hi")


async def test_transport_error_is_retried(session: AsyncSession) -> None:
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectTimeout("timed out")
        return httpx.Response(200, json=completion("recovered"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        result = await client.complete("hi")

    assert result.text == "recovered"
    assert attempts["n"] == 2


async def test_failed_attempts_are_recorded(session: AsyncSession) -> None:
    """A provider failing all day must be visible, not inferred."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="nope")

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(llm_max_attempts=2), client=http)
        with pytest.raises(LlmError):
            await client.complete("hi")

    rows = await calls_recorded(session)
    assert rows, "failures must be recorded"
    assert all(row.ok is False for row in rows)
    assert all(row.error for row in rows)


async def test_empty_message_is_an_error(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=completion("   "))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        with pytest.raises(LlmError):
            await client.complete("hi")


async def test_unexpected_response_shape_is_an_error(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": True})

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        with pytest.raises(LlmError):
            await client.complete("hi")


# --- cache -----------------------------------------------------------------


async def test_second_identical_call_is_served_from_cache(session: AsyncSession) -> None:
    hits = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        hits["n"] += 1
        return httpx.Response(200, json=completion("cached answer"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        first = await client.complete("same prompt")
        second = await client.complete("same prompt")

    assert first.text == second.text == "cached answer"
    assert second.cached is True
    assert hits["n"] == 1, "the second call must not reach the network"


async def test_cache_hit_does_not_consume_the_budget(session: AsyncSession) -> None:
    """A cached answer costs nothing, so it must not count against the limit."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=completion("answer"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(llm_daily_call_limit=1), client=http)
        await client.complete("prompt")
        # Budget is now spent; a cached answer must still be served.
        result = await client.complete("prompt")

    assert result.cached is True


async def test_different_prompts_are_cached_separately(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(200, json=completion(body["messages"][-1]["content"]))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        first = await client.complete("one")
        second = await client.complete("two")

    assert first.text == "one"
    assert second.text == "two"
    assert second.cached is False


async def test_cache_is_keyed_by_model(session: AsyncSession) -> None:
    """Two models given the same prompt are not interchangeable."""
    cache = ResponseCache(session)
    await cache.put("model-a", "prompt", "answer from a")

    assert await cache.get("model-b", "prompt") is None
    assert await cache.get("model-a", "prompt") == "answer from a"


# --- budget ----------------------------------------------------------------


async def test_budget_refuses_before_calling_the_provider(session: AsyncSession) -> None:
    """Refusing after spending would defeat the point of a budget."""
    hits = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        hits["n"] += 1
        return httpx.Response(200, json=completion("answer"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(llm_daily_call_limit=1), client=http)
        await client.complete("first")
        with pytest.raises(LlmBudgetExceeded):
            await client.complete("second")

    assert hits["n"] == 1


async def test_budget_counts_only_todays_calls(session: AsyncSession) -> None:
    guard = BudgetGuard(session, daily_limit=5)

    assert await guard.used_today() == 0
    assert await guard.remaining() == 5


async def test_budget_counts_failed_calls_too(session: AsyncSession) -> None:
    """Otherwise a broken provider looks like an idle pipeline."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="nope")

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(llm_max_attempts=1), client=http)
        with pytest.raises(LlmError):
            await client.complete("prompt")

    guard = BudgetGuard(session, daily_limit=5)
    assert await guard.used_today() >= 1


async def test_budget_rejects_a_non_positive_limit(session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="positive"):
        BudgetGuard(session, daily_limit=0)


# --- complete_json ---------------------------------------------------------


async def test_complete_json_parses_the_answer(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=json_completion({"score": 0.8}))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        payload = await client.complete_json("rate this")

    assert payload == {"score": 0.8}


async def test_complete_json_asks_again_when_the_reply_is_prose(
    session: AsyncSession,
) -> None:
    """A reasoning model can spend the whole reply thinking and never emit JSON.

    The second call must carry the model's own answer back to it: the thinking
    is already done, and starting over from the bare prompt tends to reproduce
    the same prose.
    """
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if len(bodies) == 1:
            return httpx.Response(200, json=completion("Let me think about this vacancy."))
        return httpx.Response(200, json=json_completion({"score": 0.8}))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        payload = await client.complete_json("rate this")

    assert payload == {"score": 0.8}
    assert len(bodies) == 2
    retry_prompt = bodies[1]["messages"][-1]["content"]
    assert retry_prompt.startswith("rate this")
    assert "Let me think about this vacancy." in retry_prompt


async def test_complete_json_gives_up_after_one_retry(session: AsyncSession) -> None:
    """Two prose replies in a row is a broken model, not something to retry forever."""
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=completion("Still thinking out loud."))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        with pytest.raises(LlmResponseInvalid):
            await client.complete_json("rate this")

    assert calls == 2


async def test_system_message_is_sent_when_given(session: AsyncSession) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=completion("ok"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        await client.complete("question", system="be terse")

    assert captured["messages"][0] == {"role": "system", "content": "be terse"}
    assert captured["messages"][1] == {"role": "user", "content": "question"}


async def test_json_mode_is_requested(session: AsyncSession) -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json=completion("ok"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        await client.complete("hi")

    assert captured["response_format"] == {"type": "json_object"}


async def test_cache_stores_one_row_per_prompt(session: AsyncSession) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=completion("answer"))

    async with client_for(handler) as http:
        client = LLMClient(session, settings=settings_with(), client=http)
        await client.complete("p")
        await client.complete("p")

    count = await session.execute(select(func.count()).select_from(LlmCallRow))
    assert count.scalar_one() == 1
    assert await ResponseCache(session).size() == 1
