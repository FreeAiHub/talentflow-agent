"""LLM tracing.

Two layers, deliberately:

1. **Structured JSON logs**, always on and dependency-free. Every call emits
   one line with model, tokens, latency and outcome. This is what actually gets
   read during an incident, and it works with no account and no server.
2. **Langfuse**, opt-in. Enabled only when both keys are set *and* the optional
   ``langfuse`` package is installed. Traces go to a self-hosted instance
   (Langfuse OSS is MIT-licensed and free), so client data does not leave the
   infrastructure.

Tracing never raises. A broken trace pipeline must not stop scoring — losing an
observation is an annoyance, losing a run is a bug.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from talentflow.config import Settings

logger = logging.getLogger("talentflow.llm.trace")


class Tracer:
    """Emits one structured record per LLM call."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any | None = None
        self._initialised = False

    @property
    def langfuse_enabled(self) -> bool:
        return self.settings.langfuse_enabled

    def _langfuse(self) -> Any | None:
        """Return a Langfuse client, or ``None`` if it is not usable."""
        if self._initialised:
            return self._client
        self._initialised = True

        if not self.settings.langfuse_enabled:
            return None

        try:
            from langfuse import Langfuse
        except ImportError:
            logger.warning(
                "Langfuse is configured but not installed. "
                "Install it with: uv sync --extra observability"
            )
            return None

        try:
            self._client = Langfuse(
                public_key=self.settings.langfuse_public_key,
                secret_key=self.settings.langfuse_secret_key,
                host=self.settings.langfuse_host,
            )
        except Exception as exc:  # noqa: BLE001 - tracing must never break scoring
            logger.warning("Could not initialise Langfuse, continuing without it: %s", exc)
            self._client = None

        return self._client

    def trace(
        self,
        *,
        name: str,
        model: str,
        provider: str,
        prompt: str,
        output: str,
        usage: dict[str, Any] | None = None,
        latency_ms: int = 0,
    ) -> None:
        """Record one successful call. Never raises."""
        self._log(
            {
                "event": "llm_call",
                "name": name,
                "provider": provider,
                "model": model,
                "latency_ms": latency_ms,
                "tokens_in": int((usage or {}).get("prompt_tokens") or 0),
                "tokens_out": int((usage or {}).get("completion_tokens") or 0),
            }
        )
        self._send_to_langfuse(
            name=name,
            model=model,
            provider=provider,
            prompt=prompt,
            output=output,
            usage=usage or {},
        )

    def _log(self, payload: dict[str, Any]) -> None:
        logger.info(json.dumps(payload, ensure_ascii=False))

    def _send_to_langfuse(
        self,
        *,
        name: str,
        model: str,
        provider: str,
        prompt: str,
        output: str,
        usage: dict[str, Any],
    ) -> None:
        client = self._langfuse()
        if client is None:
            return
        try:
            with client.start_as_current_observation(
                as_type="generation", name=name, model=model
            ) as generation:
                generation.update(
                    input=prompt,
                    output=output,
                    metadata={"provider": provider},
                    usage_details={
                        "input": int(usage.get("prompt_tokens") or 0),
                        "output": int(usage.get("completion_tokens") or 0),
                    },
                )
        except Exception as exc:  # noqa: BLE001 - tracing must never break scoring
            logger.warning("Langfuse trace failed, continuing: %s", exc)
