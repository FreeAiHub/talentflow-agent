"""LLM error types.

Kept in their own module so the budget guard, the client and callers can all
refer to them without importing each other.
"""

from __future__ import annotations


class LlmError(RuntimeError):
    """Base class for LLM failures."""


class LlmBudgetExceeded(LlmError):
    """The daily call budget is spent.

    Raised rather than silently continuing: a pipeline that quietly stops
    scoring looks identical to one that has nothing to score.
    """


class NoProviderConfigured(LlmError):
    """No API key is set, so no call can be made."""


class LlmResponseInvalid(LlmError):
    """Every provider answered, but none returned usable JSON."""
