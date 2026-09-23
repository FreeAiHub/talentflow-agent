"""Telegram notifications.

The channel is Telegram because it is free and it is where the target market
already works. A lead above the threshold produces one message with two
buttons; pressing one calls the same review path as the REST API, so the gate
from Day 6 applies unchanged.

Three things this module is careful about:

- **The webhook is authenticated.** Telegram echoes a secret in a header; an
  unauthenticated POST could otherwise approve drafts on someone's behalf.
- **Deliveries are deduplicated.** Telegram retries, and a replayed old
  "approve" landing after a newer "reject" would silently reverse it.
- **Sending is rate limited.** A burst of messages is how a bot gets throttled
  or muted, so the ceiling is enforced before the request, not after.
"""

from __future__ import annotations

import contextlib
import hmac
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import httpx

from talentflow.config import Settings, get_settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.telegram.org"

APPROVE = "approve"
REJECT = "reject"
ACTIONS = (APPROVE, REJECT)

#: Telegram caps a message at 4096 characters; leave room for the framing.
MAX_MESSAGE_CHARS = 3500
#: Telegram caps callback_data at 64 bytes.
MAX_CALLBACK_BYTES = 64


class TelegramError(RuntimeError):
    """A Telegram API call failed."""


class TelegramNotConfigured(TelegramError):
    """No bot token or chat id, so nothing can be sent.

    Separate from the base error because it is a configuration gap rather than
    a fault: the pipeline records the notify stage as skipped, not failed.
    """


class RateLimited(TelegramError):
    """Too many messages in the current window."""


def callback_data(action: str, application_id: int) -> str:
    """Build the payload behind a button, e.g. ``approve:12``."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}; expected one of {ACTIONS}")
    payload = f"{action}:{application_id}"
    if len(payload.encode()) > MAX_CALLBACK_BYTES:
        raise ValueError(f"callback data too long: {payload!r}")
    return payload


def parse_callback(data: str | None) -> tuple[str, int] | None:
    """Parse a button payload. Returns ``None`` for anything unrecognised.

    Returning ``None`` rather than raising: callback data arrives from outside,
    and an unexpected value is a message to ignore, not a reason to fail a
    webhook and have Telegram retry it forever.
    """
    if not data or ":" not in data:
        return None
    action, _, raw_id = data.partition(":")
    if action not in ACTIONS:
        return None
    try:
        application_id = int(raw_id)
    except ValueError:
        return None
    if application_id <= 0:
        return None
    return action, application_id


def escape_html(text: str) -> str:
    """Escape the three characters Telegram's HTML mode treats specially."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@dataclass
class LeadNotification:
    """One lead, ready to send."""

    application_id: int
    vacancy_id: str
    text: str
    approve_data: str
    reject_data: str

    def keyboard(self) -> dict[str, Any]:
        return {
            "inline_keyboard": [
                [
                    {"text": "✅ Утвердить", "callback_data": self.approve_data},
                    {"text": "❌ Отклонить", "callback_data": self.reject_data},
                ]
            ]
        }


def format_lead(
    *,
    application_id: int,
    title: str,
    company: str,
    score: float,
    reasons: list[str],
    url: str | None,
    draft: str = "",
) -> LeadNotification:
    """Render a lead as an HTML message with its buttons."""
    lines = [
        f"🎯 <b>{escape_html(title)}</b>",
        f"{escape_html(company or '—')} · оценка {score:.2f}",
    ]

    if reasons:
        lines.append("")
        lines.extend(f"• {escape_html(reason)}" for reason in reasons[:5])

    if url:
        lines.append("")
        lines.append(f'<a href="{escape_html(url)}">Открыть вакансию</a>')

    if draft:
        preview = draft[:600].rstrip()
        if len(draft) > 600:
            preview += "…"
        lines.append("")
        lines.append(f"<b>Черновик:</b>\n{escape_html(preview)}")

    lines.append("")
    lines.append("<i>Ничего не отправлено. Решение за вами.</i>")

    text = "\n".join(lines)[:MAX_MESSAGE_CHARS]

    return LeadNotification(
        application_id=application_id,
        vacancy_id="",
        text=text,
        approve_data=callback_data(APPROVE, application_id),
        reject_data=callback_data(REJECT, application_id),
    )


class MessageBudget:
    """A sliding-window ceiling on outgoing messages.

    Counted locally because Telegram's own limits are enforced by muting the
    bot, which is a slow and unpleasant way to discover the ceiling.
    """

    def __init__(self, per_minute: int) -> None:
        if per_minute <= 0:
            raise ValueError("per_minute must be positive")
        self.per_minute = per_minute
        self._sent: deque[float] = deque()

    def _trim(self, now: float) -> None:
        cutoff = now - 60.0
        while self._sent and self._sent[0] < cutoff:
            self._sent.popleft()

    def check(self, now: float | None = None) -> None:
        """Raise :class:`RateLimited` when the window is full."""
        moment = now if now is not None else time.monotonic()
        self._trim(moment)
        if len(self._sent) >= self.per_minute:
            raise RateLimited(
                f"message budget reached: {len(self._sent)}/{self.per_minute} in the last minute"
            )

    def record(self, now: float | None = None) -> None:
        self._sent.append(now if now is not None else time.monotonic())

    @property
    def sent_in_window(self) -> int:
        self._trim(time.monotonic())
        return len(self._sent)


class TelegramNotifier:
    """Sends lead notifications and answers button presses."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        budget: MessageBudget | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._client = client
        self.budget = budget or MessageBudget(self.settings.telegram_max_messages_per_minute)

    @property
    def enabled(self) -> bool:
        return self.settings.telegram_enabled

    def verify_secret(self, provided: str | None) -> bool:
        """Whether a webhook request carries the expected secret.

        Compared in constant time: a length-dependent comparison leaks the
        secret one byte at a time to anyone willing to measure.
        """
        expected = self.settings.telegram_webhook_secret
        if not expected:
            return False
        if not provided:
            return False
        return hmac.compare_digest(provided, expected)

    async def send_lead(self, notification: LeadNotification) -> bool:
        """Send one lead. Returns ``False`` when notifications are disabled."""
        if not self.enabled:
            logger.info(
                "Telegram not configured; skipping notification for application %d",
                notification.application_id,
            )
            return False

        self.budget.check()
        response = await self._post(
            "sendMessage",
            {
                "chat_id": self.settings.telegram_chat_id,
                "text": notification.text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": notification.keyboard(),
            },
        )
        self.budget.record()
        _raise_for_telegram(response)
        return True

    async def answer_callback(self, callback_query_id: str, text: str) -> None:
        """Acknowledge a button press so the client stops showing a spinner.

        Best effort by design: by the time this runs the decision is already
        stored, and failing the webhook over a missing toast would have
        Telegram retry a decision that has already been made.
        """
        if not self.enabled:
            return
        try:
            response = await self._post(
                "answerCallbackQuery",
                {"callback_query_id": callback_query_id, "text": text[:200]},
            )
            _raise_for_telegram(response)
        except (TelegramError, httpx.HTTPError) as exc:
            logger.warning("Could not acknowledge callback %s: %s", callback_query_id, exc)

    async def _post(self, method: str, payload: dict[str, Any]) -> httpx.Response:
        url = f"{API_BASE}/bot{self.settings.telegram_bot_token}/{method}"
        if self._client is not None:
            return await self._client.post(url, json=payload)
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await client.post(url, json=payload)


def _raise_for_telegram(response: httpx.Response) -> None:
    """Turn a non-OK Telegram response into a clear error."""
    if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
        retry_after = "unknown"
        with contextlib.suppress(ValueError):
            retry_after = str(response.json().get("parameters", {}).get("retry_after"))
        raise RateLimited(f"Telegram throttled us; retry after {retry_after}s")
    if response.status_code >= 400:
        raise TelegramError(f"Telegram returned HTTP {response.status_code}: {response.text[:200]}")

    try:
        body = response.json()
    except ValueError as exc:
        raise TelegramError(f"Telegram returned non-JSON: {response.text[:200]}") from exc

    if not body.get("ok", False):
        raise TelegramError(f"Telegram refused the request: {body.get('description')}")
