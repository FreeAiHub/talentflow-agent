"""Notification channels.

:mod:`talentflow.notifiers.telegram` sends a lead with approve/reject buttons and
handles the button presses. Pressing a button goes through the same review path
as the REST API, so the human-in-the-loop gate applies either way.
"""

from talentflow.notifiers.telegram import (
    APPROVE,
    REJECT,
    LeadNotification,
    MessageBudget,
    RateLimited,
    TelegramError,
    TelegramNotConfigured,
    TelegramNotifier,
    callback_data,
    escape_html,
    format_lead,
    parse_callback,
)

__all__ = [
    "APPROVE",
    "REJECT",
    "LeadNotification",
    "MessageBudget",
    "RateLimited",
    "TelegramError",
    "TelegramNotConfigured",
    "TelegramNotifier",
    "callback_data",
    "escape_html",
    "format_lead",
    "parse_callback",
]
