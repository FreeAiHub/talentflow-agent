"""Tests for Telegram notifications and the callback webhook.

No network and no real bot: the Telegram API is replaced by a mock transport,
and the webhook is exercised through the ASGI app.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.config import Settings, get_settings
from talentflow.models import Vacancy
from talentflow.notifiers import (
    APPROVE,
    REJECT,
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
from talentflow.pipeline import run_notify
from talentflow.storage import (
    create_application,
    create_draft_application,
    list_unnotified_applications,
    save_vacancies,
)

WEBHOOK_SECRET = "s3cret-token"


def telegram_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "telegram_bot_token": "123:test-token",
        "telegram_chat_id": "-100123",
        "telegram_webhook_secret": WEBHOOK_SECRET,
        "telegram_max_messages_per_minute": 20,
    }
    base.update(overrides)
    return Settings(**base)


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


def ok_response() -> httpx.Response:
    return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})


# --- callback payloads -----------------------------------------------------


def test_callback_data_round_trips() -> None:
    payload = callback_data(APPROVE, 42)

    assert parse_callback(payload) == (APPROVE, 42)


def test_callback_data_rejects_an_unknown_action() -> None:
    with pytest.raises(ValueError, match="unknown action"):
        callback_data("delete", 1)


@pytest.mark.parametrize(
    "data",
    [None, "", "approve", "approve:", ":1", "nonsense:1", "approve:abc", "approve:0", "approve:-3"],
)
def test_parse_callback_ignores_unusable_input(data: str | None) -> None:
    """Callback data arrives from outside; anything odd is ignored, not raised."""
    assert parse_callback(data) is None


def test_callback_data_stays_within_telegram_limit() -> None:
    assert len(callback_data(APPROVE, 999_999).encode()) <= 64


# --- message formatting ----------------------------------------------------


def test_escape_html_covers_the_three_special_characters() -> None:
    assert escape_html("a & b < c > d") == "a &amp; b &lt; c &gt; d"


def test_format_lead_includes_the_essentials() -> None:
    notification = format_lead(
        application_id=7,
        title="Senior Python Developer",
        company="Acme",
        score=0.88,
        reasons=["Прямой работодатель", "Стек совпадает"],
        url="https://djinni.co/jobs/1-x/",
        draft="Hi — saw your posting.",
    )

    assert "Senior Python Developer" in notification.text
    assert "Acme" in notification.text
    assert "0.88" in notification.text
    assert "Прямой работодатель" in notification.text
    assert "djinni.co" in notification.text
    assert "Ничего не отправлено" in notification.text


def test_format_lead_escapes_model_output() -> None:
    """Vacancy text is model- and market-supplied; it must not inject markup."""
    notification = format_lead(
        application_id=1,
        title="C++ <script>alert(1)</script>",
        company="A & B",
        score=0.5,
        reasons=["<b>not bold</b>"],
        url=None,
        draft="",
    )

    assert "<script>" not in notification.text
    assert "&lt;script&gt;" in notification.text
    assert "A &amp; B" in notification.text
    assert "&lt;b&gt;not bold&lt;/b&gt;" in notification.text


def test_format_lead_truncates_a_long_draft() -> None:
    notification = format_lead(
        application_id=1,
        title="T",
        company="C",
        score=0.5,
        reasons=[],
        url=None,
        draft="word " * 500,
    )

    assert len(notification.text) <= 3500
    assert "…" in notification.text


def test_format_lead_buttons_carry_approve_and_reject() -> None:
    notification = format_lead(
        application_id=13, title="T", company="C", score=0.5, reasons=[], url=None
    )

    keyboard = notification.keyboard()["inline_keyboard"][0]

    assert [button["callback_data"] for button in keyboard] == ["approve:13", "reject:13"]


def test_format_lead_omits_the_link_when_there_is_none() -> None:
    notification = format_lead(
        application_id=1, title="T", company="C", score=0.5, reasons=[], url=None
    )

    assert "<a href" not in notification.text


# --- rate limiting ---------------------------------------------------------


def test_budget_allows_up_to_the_limit() -> None:
    budget = MessageBudget(per_minute=3)

    for _ in range(3):
        budget.check()
        budget.record()

    assert budget.sent_in_window == 3


def test_budget_refuses_beyond_the_limit() -> None:
    budget = MessageBudget(per_minute=2)
    budget.record(now=1000.0)
    budget.record(now=1001.0)

    with pytest.raises(RateLimited, match="budget reached"):
        budget.check(now=1002.0)


def test_budget_window_slides() -> None:
    """Messages older than a minute stop counting."""
    budget = MessageBudget(per_minute=2)
    budget.record(now=1000.0)
    budget.record(now=1001.0)

    budget.check(now=1062.0)  # both are now outside the window


def test_budget_rejects_a_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="positive"):
        MessageBudget(per_minute=0)


# --- webhook secret --------------------------------------------------------


def test_secret_is_accepted_when_it_matches() -> None:
    notifier = TelegramNotifier(telegram_settings())

    assert notifier.verify_secret(WEBHOOK_SECRET) is True


@pytest.mark.parametrize("provided", [None, "", "wrong", WEBHOOK_SECRET + "x"])
def test_secret_is_refused_when_it_does_not_match(provided: str | None) -> None:
    notifier = TelegramNotifier(telegram_settings())

    assert notifier.verify_secret(provided) is False


def test_secret_is_refused_when_none_is_configured() -> None:
    """No secret means no way to authenticate, so nothing is accepted."""
    notifier = TelegramNotifier(telegram_settings(telegram_webhook_secret=None))

    assert notifier.verify_secret(None) is False
    assert notifier.verify_secret("anything") is False


# --- sending ---------------------------------------------------------------


async def test_send_lead_posts_the_expected_payload() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return ok_response()

    notification = format_lead(
        application_id=5, title="T", company="C", score=0.9, reasons=["r"], url=None
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = TelegramNotifier(telegram_settings(), client=client)
        sent = await notifier.send_lead(notification)

    assert sent is True
    assert "/bot123:test-token/sendMessage" in captured["url"]
    assert captured["body"]["chat_id"] == "-100123"
    assert captured["body"]["parse_mode"] == "HTML"
    assert captured["body"]["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "approve:5"


async def test_send_lead_does_nothing_when_not_configured() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("no request should be made")

    notification = format_lead(
        application_id=1, title="T", company="C", score=0.5, reasons=[], url=None
    )
    settings = telegram_settings(telegram_bot_token=None, telegram_chat_id=None)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = TelegramNotifier(settings, client=client)
        sent = await notifier.send_lead(notification)

    assert sent is False


async def test_send_lead_raises_on_telegram_throttling() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 12}})

    notification = format_lead(
        application_id=1, title="T", company="C", score=0.5, reasons=[], url=None
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = TelegramNotifier(telegram_settings(), client=client)
        with pytest.raises(RateLimited, match="retry after 12s"):
            await notifier.send_lead(notification)


async def test_send_lead_raises_when_telegram_says_not_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": False, "description": "chat not found"})

    notification = format_lead(
        application_id=1, title="T", company="C", score=0.5, reasons=[], url=None
    )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = TelegramNotifier(telegram_settings(), client=client)
        with pytest.raises(TelegramError, match="chat not found"):
            await notifier.send_lead(notification)


async def test_send_lead_respects_the_budget() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return ok_response()

    notification = format_lead(
        application_id=1, title="T", company="C", score=0.5, reasons=[], url=None
    )
    settings = telegram_settings(telegram_max_messages_per_minute=1)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        notifier = TelegramNotifier(settings, client=client)
        await notifier.send_lead(notification)
        with pytest.raises(RateLimited):
            await notifier.send_lead(notification)


# --- notify stage ----------------------------------------------------------


async def test_notify_stage_refuses_without_configuration(session: AsyncSession) -> None:
    """A missing token is a configuration gap, which the pipeline records as skipped."""
    settings = Settings(telegram_bot_token=None, telegram_chat_id=None)

    with pytest.raises(TelegramNotConfigured):
        await run_notify(session, settings)


async def test_notified_drafts_are_not_sent_twice(session: AsyncSession) -> None:
    await save_vacancies(session, [vacancy("1")])
    await create_application(session, "1", "draft")

    first = await list_unnotified_applications(session)
    assert len(first) == 1

    from talentflow.storage import mark_notified

    await mark_notified(session, first[0].id)

    assert await list_unnotified_applications(session) == []


async def test_decided_drafts_are_not_notified(session: AsyncSession) -> None:
    """Only pending drafts are worth the reviewer's attention."""
    await save_vacancies(session, [vacancy("1")])
    await create_draft_application(session, "1", "invented", sendable=False)

    assert await list_unnotified_applications(session) == []


# --- webhook endpoint ------------------------------------------------------


@pytest.fixture
def telegram_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Point the app at a configured bot for the duration of a test."""
    monkeypatch.setenv("TALENTFLOW_TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setenv("TALENTFLOW_TELEGRAM_CHAT_ID", "-100123")
    monkeypatch.setenv("TALENTFLOW_TELEGRAM_WEBHOOK_SECRET", WEBHOOK_SECRET)
    get_settings.cache_clear()

    from talentflow.api.main import app, get_notifier

    async def _noop(request: httpx.Request) -> httpx.Response:
        return ok_response()

    client = httpx.AsyncClient(transport=httpx.MockTransport(_noop))
    app.dependency_overrides[get_notifier] = lambda: TelegramNotifier(get_settings(), client=client)
    yield
    app.dependency_overrides.pop(get_notifier, None)
    get_settings.cache_clear()


def update_body(update_id: int, data: str | None) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "callback_query": {"id": f"cb-{update_id}", "data": data},
    }


async def _reload(session: AsyncSession, application_id: int) -> Any:
    """Re-read a row the webhook may have changed.

    The webhook commits through its own session, while this one still holds the
    pre-webhook instance. ``populate_existing`` forces the row to be refreshed
    instead of handed back from the identity map.
    """
    from sqlalchemy import select

    from talentflow.storage.tables import ApplicationRow

    result = await session.execute(
        select(ApplicationRow)
        .where(ApplicationRow.id == application_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


async def test_webhook_refuses_a_missing_secret(
    api_client: httpx.AsyncClient, telegram_env: None
) -> None:
    """Without the secret, anyone could approve drafts by posting here."""
    response = await api_client.post("/webhooks/telegram", json=update_body(1, "approve:1"))

    assert response.status_code == 403


async def test_webhook_refuses_a_wrong_secret(
    api_client: httpx.AsyncClient, telegram_env: None
) -> None:
    response = await api_client.post(
        "/webhooks/telegram",
        json=update_body(1, "approve:1"),
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )

    assert response.status_code == 403


async def test_webhook_approves_a_draft(
    api_client: httpx.AsyncClient, session: AsyncSession, telegram_env: None
) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_application(session, "1", "draft")

    response = await api_client.post(
        "/webhooks/telegram",
        json=update_body(10, f"approve:{application.id}"),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert response.status_code == 200
    assert response.json()["result"] == "approved"

    stored = await _reload(session, application.id)
    assert stored.status == "approved"


async def test_webhook_rejects_a_draft(
    api_client: httpx.AsyncClient, session: AsyncSession, telegram_env: None
) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_application(session, "1", "draft")

    response = await api_client.post(
        "/webhooks/telegram",
        json=update_body(11, f"{REJECT}:{application.id}"),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert response.json()["result"] == "rejected"


async def test_replayed_update_does_not_reverse_a_decision(
    api_client: httpx.AsyncClient, session: AsyncSession, telegram_env: None
) -> None:
    """Telegram retries; an old approval must not undo a newer rejection."""
    await save_vacancies(session, [vacancy("1")])
    application = await create_application(session, "1", "draft")
    headers = {"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET}

    await api_client.post(
        "/webhooks/telegram",
        json=update_body(20, f"approve:{application.id}"),
        headers=headers,
    )
    await api_client.post(
        "/webhooks/telegram",
        json=update_body(21, f"reject:{application.id}"),
        headers=headers,
    )
    # The first delivery arrives again, out of order.
    replay = await api_client.post(
        "/webhooks/telegram",
        json=update_body(20, f"approve:{application.id}"),
        headers=headers,
    )

    assert replay.json()["reason"] == "duplicate update"

    stored = await _reload(session, application.id)
    assert stored.status == "rejected", "the replay must not have re-approved it"


async def test_webhook_refuses_a_grounding_failed_draft(
    api_client: httpx.AsyncClient, session: AsyncSession, telegram_env: None
) -> None:
    await save_vacancies(session, [vacancy("1")])
    application = await create_draft_application(session, "1", "invented", sendable=False)

    response = await api_client.post(
        "/webhooks/telegram",
        json=update_body(30, f"approve:{application.id}"),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert response.json()["result"] == "refused"
    assert "grounding check" in response.json()["reason"]


async def test_webhook_ignores_unrecognised_callback_data(
    api_client: httpx.AsyncClient, telegram_env: None
) -> None:
    response = await api_client.post(
        "/webhooks/telegram",
        json=update_body(40, "do-something-else"),
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert response.json()["handled"] is False


async def test_webhook_ignores_updates_without_a_callback(
    api_client: httpx.AsyncClient, telegram_env: None
) -> None:
    response = await api_client.post(
        "/webhooks/telegram",
        json={"update_id": 50},
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert response.json() == {"ok": True, "handled": False}


async def test_webhook_rejects_a_malformed_body(
    api_client: httpx.AsyncClient, telegram_env: None
) -> None:
    response = await api_client.post(
        "/webhooks/telegram",
        json={"nonsense": True},
        headers={"X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET},
    )

    assert response.status_code == 422


async def test_webhook_duplicate_claim_is_atomic(session: AsyncSession) -> None:
    """The primary key decides the winner, so two deliveries cannot both pass."""
    from talentflow.storage import claim_telegram_update

    assert await claim_telegram_update(session, 99, action="approve") is True
    assert await claim_telegram_update(session, 99, action="approve") is False
