"""Tests for deployment concerns: webhook authentication and prompt resolution."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from talentflow.api.main import verify_vapi_secret
from talentflow.config import get_settings
from talentflow.llm.prompts import candidate_prompt_dirs, load_prompt, prompts_dir

VAPI_SECRET = "vapi-test-secret"


# --- Vapi secret comparison ------------------------------------------------


def test_vapi_secret_matches() -> None:
    assert verify_vapi_secret(VAPI_SECRET, VAPI_SECRET) is True


@pytest.mark.parametrize("provided", [None, "", "wrong", VAPI_SECRET + "x", VAPI_SECRET[:-1]])
def test_vapi_secret_rejects_anything_else(provided: str | None) -> None:
    assert verify_vapi_secret(provided, VAPI_SECRET) is False


def test_vapi_secret_rejects_everything_when_unconfigured() -> None:
    """No configured secret means no request can be authenticated."""
    assert verify_vapi_secret("anything", None) is False
    assert verify_vapi_secret(None, None) is False


# --- Vapi webhook ----------------------------------------------------------


@pytest.fixture
def vapi_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("TALENTFLOW_VAPI_WEBHOOK_SECRET", VAPI_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def unconfigured_vapi_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.delenv("TALENTFLOW_VAPI_WEBHOOK_SECRET", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_vapi_webhook_accepts_the_right_secret(
    api_client: httpx.AsyncClient, vapi_env: None
) -> None:
    response = await api_client.post(
        "/webhooks/vapi",
        json={"event": "call.ended", "payload": {}},
        headers={"X-Vapi-Signature": VAPI_SECRET},
    )

    assert response.status_code == 200
    assert response.json() == {"received": "call.ended"}


async def test_vapi_webhook_rejects_a_missing_header(
    api_client: httpx.AsyncClient, vapi_env: None
) -> None:
    """This endpoint used to accept anything that knew the URL."""
    response = await api_client.post("/webhooks/vapi", json={"event": "call.ended"})

    assert response.status_code == 401


async def test_vapi_webhook_rejects_a_wrong_secret(
    api_client: httpx.AsyncClient, vapi_env: None
) -> None:
    response = await api_client.post(
        "/webhooks/vapi",
        json={"event": "call.ended"},
        headers={"X-Vapi-Signature": "not-the-secret"},
    )

    assert response.status_code == 401


async def test_vapi_webhook_fails_closed_when_unconfigured(
    api_client: httpx.AsyncClient, unconfigured_vapi_env: None
) -> None:
    """503, not 200: an unconfigured endpoint must not quietly accept traffic."""
    response = await api_client.post(
        "/webhooks/vapi",
        json={"event": "call.ended"},
        headers={"X-Vapi-Signature": "anything"},
    )

    assert response.status_code == 503
    assert "TALENTFLOW_VAPI_WEBHOOK_SECRET" in response.json()["detail"]


# --- prompt resolution -----------------------------------------------------


def test_prompt_search_covers_the_container_layout() -> None:
    """Inside a wheel the package sits in site-packages, not at the repo root."""
    candidates = [str(path) for path in candidate_prompt_dirs()]

    assert any(path.endswith("/app/prompts") for path in candidates), (
        "the container path must be searched, or a deployed image finds no prompts"
    )
    assert any(path.endswith("prompts") and "/site-packages/" not in path for path in candidates)


def test_prompts_are_found_in_a_source_checkout() -> None:
    assert prompts_dir().is_dir()
    assert load_prompt("vacancy_scorer")


def test_prompts_dir_honours_the_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TALENTFLOW_PROMPTS_DIR", str(tmp_path))

    assert prompts_dir() == tmp_path


def test_override_wins_even_when_it_does_not_exist(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An explicit setting is a decision, not a hint to be second-guessed."""
    missing = tmp_path / "nope"
    monkeypatch.setenv("TALENTFLOW_PROMPTS_DIR", str(missing))

    assert prompts_dir() == missing


def test_missing_prompt_lists_where_it_looked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("TALENTFLOW_PROMPTS_DIR", str(tmp_path))

    from talentflow.llm.prompts import PromptNotFound

    with pytest.raises(PromptNotFound) as excinfo:
        load_prompt("does_not_exist")

    assert "Searched" in str(excinfo.value)
    assert str(tmp_path) in str(excinfo.value)


def test_every_referenced_prompt_exists() -> None:
    """Catch a renamed prompt file before it fails at runtime."""
    referenced: dict[str, Any] = {
        "vacancy_scorer": None,
        "response_generator": None,
        "grounding_checker": None,
    }

    for name in referenced:
        assert load_prompt(name), f"{name}.md is missing or empty"
