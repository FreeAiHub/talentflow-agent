"""LLM access layer.

- :mod:`talentflow.llm.client` — the client: provider chain, retries, JSON parsing
- :mod:`talentflow.llm.guard` — daily call budget and response cache
- :mod:`talentflow.llm.errors` — exception types
- :mod:`talentflow.llm.tracing` — structured logs plus optional Langfuse
"""

from talentflow.llm.client import LLMClient, LlmResult, ModelRef, Provider, extract_json
from talentflow.llm.errors import (
    LlmBudgetExceeded,
    LlmError,
    LlmResponseInvalid,
    NoProviderConfigured,
)
from talentflow.llm.guard import BudgetGuard, ResponseCache, prompt_hash, record_call

__all__ = [
    "BudgetGuard",
    "LLMClient",
    "LlmBudgetExceeded",
    "LlmError",
    "LlmResponseInvalid",
    "LlmResult",
    "ModelRef",
    "NoProviderConfigured",
    "Provider",
    "ResponseCache",
    "extract_json",
    "prompt_hash",
    "record_call",
]
