"""LLM access: one client, a chain of providers, and a hard daily budget.

All three providers speak the OpenAI chat-completions shape, so a single
implementation covers them and adding a fourth is a config line.

The chain exists for a concrete reason: OpenRouter's free tier allows only 50
calls a day, while the pipeline needs roughly 250. Groq and Cerebras give
1000 calls and ~1M tokens a day free respectively, so a request that OpenRouter
refuses is retried against them instead of failing the run.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.config import Settings, get_settings
from talentflow.llm.errors import (
    LlmError,
    LlmResponseInvalid,
    NoProviderConfigured,
)
from talentflow.llm.guard import BudgetGuard, ResponseCache, prompt_hash, record_call
from talentflow.llm.tracing import Tracer

logger = logging.getLogger(__name__)

#: JSON is sometimes wrapped in a fenced code block despite instructions.
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)

#: Appended to the prompt when a first reply carried no usable JSON. The model is
#: shown its own answer so the second attempt continues from the thinking it
#: already did instead of starting over.
REPAIR_SUFFIX = (
    "\n\n---\n\n"
    "Your previous reply was not a JSON object, so it could not be used. "
    "Reply again with the JSON object alone: no explanation, no reasoning, "
    "no markdown fence, nothing before or after it.\n\n"
    "Your previous reply was:\n\n{previous}\n"
)


@dataclass(frozen=True)
class Provider:
    """An OpenAI-compatible endpoint."""

    name: str
    base_url: str
    api_key: str


@dataclass(frozen=True)
class ModelRef:
    """A ``provider:model`` pair from configuration."""

    provider: str
    model: str

    @classmethod
    def parse(cls, raw: str) -> ModelRef:
        """Parse ``"openrouter:openai/gpt-oss-120b:free"``.

        Splits on the first colon only, so model ids containing colons (which
        OpenRouter uses for its ``:free`` suffix) survive intact.
        """
        provider, _, model = raw.partition(":")
        if not provider or not model:
            raise ValueError(f"model must look like 'provider:model', got {raw!r}")
        return cls(provider=provider.strip(), model=model.strip())


@dataclass
class LlmResult:
    """A completion, plus what it cost."""

    text: str
    model: str
    provider: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    cached: bool = False


def extract_json(text: str) -> Any:
    """Parse JSON from a model response, tolerating a fenced code block.

    Raises :class:`LlmResponseInvalid` rather than returning ``None``: a caller
    that forgets to check for ``None`` would treat a malformed answer as a
    score of zero.
    """
    candidate = text.strip()
    fenced = _FENCE.match(candidate)
    if fenced:
        candidate = fenced.group(1)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Last resort: a short preamble before the object is common enough to
        # be worth one bounded attempt.
        start, end = candidate.find("{"), candidate.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(candidate[start : end + 1])
            except json.JSONDecodeError:
                pass
    raise LlmResponseInvalid(f"could not parse JSON from response: {text[:200]!r}")


class Completer(Protocol):
    """Anything that can answer a prompt.

    The scorer depends on this, not on :class:`LLMClient`: it needs one method,
    and narrowing the dependency is what lets a stub stand in during tests.
    """

    async def complete(self, prompt: str, *, system: str | None = None) -> LlmResult: ...


class LLMClient:
    """Send prompts to a chain of providers under a daily budget.

    Order of operations for each request:

    1. Cache lookup — a hit costs nothing and does not count against the budget.
    2. Budget check — refuse before spending, not after.
    3. Providers, in order, with retries on transient failures.
    4. Record the call (success or failure) and cache the response.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        client: httpx.AsyncClient | None = None,
        purpose: str = "unknown",
    ) -> None:
        self.settings = settings or get_settings()
        self.session = session
        self.purpose = purpose
        self._client = client
        self._budget = BudgetGuard(session, self.settings.llm_daily_call_limit)
        self._cache = ResponseCache(session)
        self._tracer = Tracer(self.settings)

    @property
    def chain(self) -> list[ModelRef]:
        return [ModelRef.parse(raw) for raw in self.settings.model_chain]

    def providers(self) -> dict[str, Provider]:
        """Configured providers, keyed by name. Providers without a key are absent."""
        configured = {
            "openrouter": (
                "https://openrouter.ai/api/v1",
                self.settings.openrouter_api_key,
            ),
            "groq": ("https://api.groq.com/openai/v1", self.settings.groq_api_key),
            "cerebras": ("https://api.cerebras.ai/v1", self.settings.cerebras_api_key),
        }
        return {
            name: Provider(name=name, base_url=base_url, api_key=key)
            for name, (base_url, key) in configured.items()
            if key
        }

    async def complete(self, prompt: str, *, system: str | None = None) -> LlmResult:
        """Run ``prompt`` through the chain, returning the first usable answer."""
        chain = self.chain
        if not chain:
            raise NoProviderConfigured("no models configured (TALENTFLOW_LLM_MODELS)")

        providers = self.providers()
        if not providers:
            raise NoProviderConfigured(
                "no API key configured: set one of TALENTFLOW_OPENROUTER_API_KEY, "
                "TALENTFLOW_GROQ_API_KEY or TALENTFLOW_CEREBRAS_API_KEY"
            )

        # A cached answer is free, so it is checked before the budget.
        for ref in chain:
            cached = await self._cache.get(ref.model, prompt)
            if cached is not None:
                return LlmResult(text=cached, model=ref.model, provider="cache", cached=True)

        await self._budget.check()

        errors: list[str] = []
        for ref in chain:
            provider = providers.get(ref.provider)
            if provider is None:
                errors.append(f"{ref.provider}: no API key configured")
                continue
            try:
                result = await self._call_provider(provider, ref.model, prompt, system)
            except LlmError as exc:
                errors.append(f"{ref.provider}/{ref.model}: {exc}")
                logger.warning("Provider %s failed: %s", ref.provider, exc)
                continue

            await self._cache.put(ref.model, prompt, result.text)
            return result

        raise LlmError("every provider failed — " + "; ".join(errors))

    async def complete_json(self, prompt: str, *, system: str | None = None) -> Any:
        """Like :meth:`complete`, but parse the answer as JSON.

        Free models answer without JSON often enough to matter: a reasoning model
        can spend the whole reply thinking out loud and never emit an object, and
        ``response_format`` is a request, not a guarantee. Rather than pick a
        model that behaves and hope it keeps behaving, a reply that does not
        parse is shown back to the model once with a request to answer again.
        The retry is a different prompt, so it is a separate cache entry and a
        separate call against the budget — it only happens on failure.
        """
        result = await self.complete(prompt, system=system)
        try:
            return extract_json(result.text)
        except LlmResponseInvalid as invalid:
            logger.warning(
                "Model %s answered without usable JSON (%s); asking once more",
                result.model,
                invalid,
            )
            retry = prompt + REPAIR_SUFFIX.format(previous=result.text[:4000])
            second = await self.complete(retry, system=system)
            return extract_json(second.text)

    async def _call_provider(
        self, provider: Provider, model: str, prompt: str, system: str | None
    ) -> LlmResult:
        """Call one provider, retrying transient failures."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
            "max_tokens": self.settings.llm_max_tokens,
            # Not every free model honours this, which is why the response is
            # validated on our side too rather than trusted.
            "response_format": {"type": "json_object"},
        }

        last_error = "no attempt made"
        for _attempt in range(1, self.settings.llm_max_attempts + 1):
            started = time.monotonic()
            try:
                response = await self._post(provider, payload)
            except httpx.HTTPError as exc:
                last_error = f"transport error: {exc}"
                await self._record(provider, model, prompt, ok=False, error=last_error)
                continue

            latency_ms = int((time.monotonic() - started) * 1000)

            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                last_error = "rate limited (429)"
                await self._record(
                    provider, model, prompt, ok=False, error=last_error, latency_ms=latency_ms
                )
                # No point retrying a rate limit on the same provider: move on.
                raise LlmError(last_error)
            if response.status_code >= 400:
                last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                await self._record(
                    provider, model, prompt, ok=False, error=last_error, latency_ms=latency_ms
                )
                continue

            body = response.json()
            text = _first_message(body)
            usage = body.get("usage") or {}

            await self._record(
                provider,
                model,
                prompt,
                ok=True,
                tokens_in=int(usage.get("prompt_tokens") or 0),
                tokens_out=int(usage.get("completion_tokens") or 0),
                latency_ms=latency_ms,
            )
            self._tracer.trace(
                name=self.purpose,
                model=model,
                provider=provider.name,
                prompt=prompt,
                output=text,
                usage=usage,
                latency_ms=latency_ms,
            )
            return LlmResult(
                text=text,
                model=model,
                provider=provider.name,
                tokens_in=int(usage.get("prompt_tokens") or 0),
                tokens_out=int(usage.get("completion_tokens") or 0),
                latency_ms=latency_ms,
            )

        raise LlmError(f"gave up after {self.settings.llm_max_attempts} attempts: {last_error}")

    async def _post(self, provider: Provider, payload: dict[str, Any]) -> httpx.Response:
        if self._client is not None:
            return await self._client.post(
                f"{provider.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {provider.api_key}"},
            )
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            return await client.post(
                f"{provider.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {provider.api_key}"},
            )

    async def _record(
        self,
        provider: Provider,
        model: str,
        prompt: str,
        *,
        ok: bool,
        error: str | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: int = 0,
    ) -> None:
        await record_call(
            self.session,
            provider=provider.name,
            model=model,
            purpose=self.purpose,
            prompt_hash=prompt_hash(model, prompt),
            ok=ok,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            error=error,
        )


def _first_message(body: dict[str, Any]) -> str:
    """Pull the assistant text out of a chat-completions response."""
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError(f"unexpected response shape: {str(body)[:200]}") from exc
    if not isinstance(content, str) or not content.strip():
        raise LlmError("model returned an empty message")
    return content
