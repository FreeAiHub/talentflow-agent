"""Tests for the Djinni parser.

Everything here runs against a recorded listing page — no network access, so
these tests behave the same locally and in CI.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from talentflow.models import Vacancy
from talentflow.parsers.djinni import (
    LISTING_URL,
    SOURCE,
    DjinniParser,
    DjinniRateLimited,
    extract_job_postings,
    to_vacancy,
)

FIXTURE = Path(__file__).parent / "fixtures" / "djinni_jobs_page1.html"
EXPECTED_POSTINGS = 15

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(scope="module")
def listing_html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def raw_posting(listing_html: str) -> dict[str, Any]:
    """The first real JobPosting from the recorded page."""
    return extract_job_postings(listing_html)[0]


def _client(handler: Handler) -> httpx.AsyncClient:
    """An httpx client wired to a mock transport — no sockets involved."""
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _synthetic_page(start_id: int, count: int = EXPECTED_POSTINGS) -> str:
    """Build a minimal listing page with distinct ids, for pagination tests."""
    postings = [
        {
            "@type": "JobPosting",
            "identifier": start_id + offset,
            "title": f"Vacancy {start_id + offset}",
            "hiringOrganization": {"@type": "Organization", "name": "Acme"},
            "url": f"https://djinni.co/jobs/{start_id + offset}-vacancy/",
            "description": "Some description",
            "datePosted": "2026-09-23T15:22:11.260185",
        }
        for offset in range(count)
    ]
    return f'<html><script type="application/ld+json">{json.dumps(postings)}</script></html>'


def _fast_parser(client: httpx.AsyncClient, limit: int = 50) -> DjinniParser:
    """A parser with all waiting removed, so tests stay instant."""
    return DjinniParser(limit=limit, client=client, request_delay=0, backoff_base=0)


# --- extraction ------------------------------------------------------------


def test_fixture_is_present() -> None:
    assert FIXTURE.is_file(), f"missing fixture: {FIXTURE}"


def test_extract_finds_every_posting(listing_html: str) -> None:
    postings = extract_job_postings(listing_html)

    assert len(postings) == EXPECTED_POSTINGS
    assert all(p["@type"] == "JobPosting" for p in postings)


def test_extract_ignores_unparsable_block() -> None:
    html = '<script type="application/ld+json">{not json}</script>'

    assert extract_job_postings(html) == []


def test_extract_skips_non_jobposting_entries() -> None:
    payload = json.dumps([{"@type": "Organization"}, {"@type": "JobPosting", "title": "x"}])
    html = f'<script type="application/ld+json">{payload}</script>'

    assert len(extract_job_postings(html)) == 1


def test_extract_accepts_object_not_wrapped_in_list() -> None:
    payload = json.dumps({"@type": "JobPosting", "title": "x"})
    html = f'<script type="application/ld+json">{payload}</script>'

    assert len(extract_job_postings(html)) == 1


def test_extract_returns_empty_for_page_without_ld_json() -> None:
    assert extract_job_postings("<html><body>Nothing here</body></html>") == []


# --- mapping ---------------------------------------------------------------


def test_to_vacancy_maps_real_posting(raw_posting: dict[str, Any]) -> None:
    vacancy = to_vacancy(raw_posting)

    assert vacancy is not None
    assert vacancy.id == str(raw_posting["identifier"])
    assert vacancy.title == raw_posting["title"]
    assert vacancy.company == raw_posting["hiringOrganization"]["name"]
    assert str(vacancy.url) == raw_posting["url"]
    assert vacancy.source == SOURCE
    assert vacancy.description


def test_every_fixture_posting_maps_completely(listing_html: str) -> None:
    """Fail loudly if Djinni stops sending a field we depend on."""
    for raw in extract_job_postings(listing_html):
        vacancy = to_vacancy(raw)

        assert vacancy is not None
        assert vacancy.id
        assert vacancy.title
        assert vacancy.company
        assert vacancy.url is not None
        assert vacancy.description
        assert vacancy.posted_at is not None


def test_posted_at_is_parsed_as_datetime(raw_posting: dict[str, Any]) -> None:
    vacancy = to_vacancy(raw_posting)

    assert vacancy is not None
    assert isinstance(vacancy.posted_at, datetime)


def test_identifier_accepts_property_value_object() -> None:
    """schema.org allows {"@type": "PropertyValue", "value": ...}."""
    raw = {
        "title": "QA Engineer",
        "identifier": {"@type": "PropertyValue", "value": 12345},
        "hiringOrganization": {"name": "Acme"},
    }

    vacancy = to_vacancy(raw)

    assert vacancy is not None
    assert vacancy.id == "12345"


@pytest.mark.parametrize(
    "raw",
    [
        {"title": "No id", "hiringOrganization": {"name": "Acme"}},
        {"identifier": 1, "hiringOrganization": {"name": "Acme"}},
        {"identifier": 1, "title": "   "},
        {"identifier": None, "title": "x"},
        {"identifier": True, "title": "x"},
    ],
)
def test_to_vacancy_skips_postings_without_id_or_title(raw: dict[str, Any]) -> None:
    assert to_vacancy(raw) is None


def test_to_vacancy_survives_missing_and_mistyped_fields() -> None:
    """One malformed record must not abort a run of hundreds."""
    raw: dict[str, Any] = {
        "identifier": 7,
        "title": "Backend Engineer",
        "hiringOrganization": "not-a-dict",
        "url": None,
        "datePosted": "not-a-date",
        "description": 12345,
    }

    vacancy = to_vacancy(raw)

    assert vacancy is not None
    assert vacancy.company == ""
    assert vacancy.description == ""
    assert vacancy.url is None
    assert vacancy.posted_at is None


def test_to_vacancy_rejects_unparsable_url() -> None:
    raw = {"identifier": 8, "title": "Dev", "url": "not a url"}

    assert to_vacancy(raw) is None


# --- collection ------------------------------------------------------------


async def test_collect_reads_from_listing_offline(listing_html: str) -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, text=listing_html)

    async with _client(handler) as client:
        vacancies = await _fast_parser(client, limit=10).collect()

    assert len(vacancies) == 10
    assert all(isinstance(v, Vacancy) for v in vacancies)
    assert seen == [LISTING_URL]


async def test_collect_does_not_request_more_pages_than_needed() -> None:
    """A limit satisfied by page 1 must not trigger a second request."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return httpx.Response(200, text=_synthetic_page(1))

    async with _client(handler) as client:
        vacancies = await _fast_parser(client, limit=5).collect()

    assert len(vacancies) == 5
    assert requested == [LISTING_URL]


async def test_collect_stops_when_a_page_adds_nothing_new(listing_html: str) -> None:
    """The same page served twice yields one page of results, not duplicates."""
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        return httpx.Response(200, text=listing_html)

    async with _client(handler) as client:
        vacancies = await _fast_parser(client, limit=100).collect()

    assert len(vacancies) == EXPECTED_POSTINGS
    assert len(requests) == 2  # page 1, then page 2 which added nothing


async def test_collect_paginates_until_limit() -> None:
    """Page 1 yields 15, so reaching 20 needs exactly one more page."""
    requested: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        requested.append(page)
        return httpx.Response(200, text=_synthetic_page(1 + (page - 1) * EXPECTED_POSTINGS))

    async with _client(handler) as client:
        vacancies = await _fast_parser(client, limit=20).collect()

    assert requested == [1, 2]
    assert len(vacancies) == 20
    assert len({v.id for v in vacancies}) == 20


async def test_collect_uses_page_param_only_after_first_page() -> None:
    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "1"))
        urls.append(str(request.url))
        return httpx.Response(200, text=_synthetic_page(1 + (page - 1) * EXPECTED_POSTINGS))

    async with _client(handler) as client:
        await _fast_parser(client, limit=20).collect()

    assert urls[0] == LISTING_URL
    assert "page=2" in urls[1]


async def test_collect_deduplicates_by_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_synthetic_page(1))

    async with _client(handler) as client:
        vacancies = await _fast_parser(client, limit=100).collect()

    ids = [v.id for v in vacancies]
    assert len(ids) == EXPECTED_POSTINGS
    assert len(ids) == len(set(ids))


async def test_collect_raises_on_rate_limit() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    async with _client(handler) as client:
        with pytest.raises(DjinniRateLimited):
            await _fast_parser(client, limit=5).collect()


async def test_collect_keeps_partial_results_when_a_page_fails(listing_html: str) -> None:
    """A failing page stops collection but keeps what was already gathered."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(200, text=listing_html)
        return httpx.Response(500)

    async with _client(handler) as client:
        vacancies = await _fast_parser(client, limit=100).collect()

    assert len(vacancies) == EXPECTED_POSTINGS


async def test_collect_retries_before_giving_up(listing_html: str) -> None:
    """Two failures then success on the third attempt still yields results."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, text=listing_html)

    async with _client(handler) as client:
        vacancies = await _fast_parser(client, limit=5).collect()

    assert calls["n"] == 3
    assert len(vacancies) == 5


async def test_collect_survives_transport_error(listing_html: str) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectTimeout("timed out")
        return httpx.Response(200, text=listing_html)

    async with _client(handler) as client:
        vacancies = await _fast_parser(client, limit=5).collect()

    assert len(vacancies) == 5


async def test_collect_returns_empty_when_every_attempt_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    async with _client(handler) as client:
        vacancies = await _fast_parser(client, limit=5).collect()

    assert vacancies == []


# --- constructor -----------------------------------------------------------


@pytest.mark.parametrize(
    ("limit", "delay", "backoff"),
    [(0, 0, 0), (-1, 0, 0), (5, -1, 0), (5, 0, -1)],
)
def test_constructor_rejects_bad_arguments(limit: int, delay: float, backoff: float) -> None:
    with pytest.raises(ValueError, match="must"):
        DjinniParser(limit=limit, request_delay=delay, backoff_base=backoff)


def test_constructor_sends_honest_user_agent() -> None:
    """The default client must identify us rather than impersonating a browser."""
    from talentflow.parsers.djinni import USER_AGENT

    assert "TalentFlowBot" in USER_AGENT
    assert "http" in USER_AGENT
