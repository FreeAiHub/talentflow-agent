"""Spending guards: the daily call budget and the response cache.

Both answer the same question — *should this call happen at all?* — and both
are persisted, so a restarted process neither forgets what it spent nor pays
twice for the same answer.
"""

from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.llm.errors import LlmBudgetExceeded
from talentflow.storage.tables import LlmCacheRow, LlmCallRow, start_of_utc_day


def prompt_hash(model: str, prompt: str) -> str:
    """Cache key for a (model, prompt) pair.

    The model is part of the key on purpose: two models given identical text
    are not interchangeable, and sharing a cache entry between them would
    silently serve one model's answer as another's.
    """
    return hashlib.sha256(f"{model}\x00{prompt}".encode()).hexdigest()


class BudgetGuard:
    """Counts calls made today and refuses to exceed the configured ceiling."""

    def __init__(self, session: AsyncSession, daily_limit: int) -> None:
        if daily_limit <= 0:
            raise ValueError("daily_limit must be positive")
        self.session = session
        self.daily_limit = daily_limit

    async def used_today(self) -> int:
        """How many calls have been attempted since midnight UTC.

        Failed attempts count: a provider answering 429 all day must not look
        like an idle pipeline.
        """
        result = await self.session.execute(
            select(func.count())
            .select_from(LlmCallRow)
            .where(LlmCallRow.called_at >= start_of_utc_day())
        )
        return int(result.scalar_one())

    async def remaining(self) -> int:
        """Calls still available today, never negative."""
        return max(0, self.daily_limit - await self.used_today())

    async def check(self) -> None:
        """Raise :class:`LlmBudgetExceeded` when the budget is spent."""
        used = await self.used_today()
        if used >= self.daily_limit:
            raise LlmBudgetExceeded(
                f"daily LLM call budget reached: {used}/{self.daily_limit}. "
                "Scoring stops until the counter resets at midnight UTC."
            )


class ResponseCache:
    """Stores model answers so the same prompt is never paid for twice."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, model: str, prompt: str) -> str | None:
        """Return a cached answer, or ``None``."""
        key = prompt_hash(model, prompt)
        result = await self.session.execute(
            select(LlmCacheRow.response).where(LlmCacheRow.key == key)
        )
        return result.scalar_one_or_none()

    async def put(self, model: str, prompt: str, response: str) -> None:
        """Cache an answer, replacing any previous entry for the same key."""
        key = prompt_hash(model, prompt)
        existing = await self.session.get(LlmCacheRow, key)
        if existing is None:
            self.session.add(LlmCacheRow(key=key, model=model, response=response))
        else:
            existing.response = response
        await self.session.commit()

    async def size(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(LlmCacheRow))
        return int(result.scalar_one())


async def record_call(
    session: AsyncSession,
    *,
    provider: str,
    model: str,
    purpose: str,
    prompt_hash: str,
    ok: bool,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    latency_ms: int = 0,
    error: str | None = None,
) -> LlmCallRow:
    """Persist one LLM call. Both successes and failures are recorded."""
    row = LlmCallRow(
        provider=provider,
        model=model,
        purpose=purpose,
        prompt_hash=prompt_hash,
        ok=ok,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_usd=cost_usd,
        latency_ms=latency_ms,
        error=error,
    )
    session.add(row)
    await session.commit()
    return row
