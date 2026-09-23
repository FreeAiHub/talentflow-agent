"""Djinni.co vacancy parser.

Djinni embeds structured data in its listing pages: a
``<script type="application/ld+json">`` block holding an array of schema.org
``JobPosting`` objects. We read that JSON instead of scraping HTML/CSS, which
survives markup changes and — because the full description ships with the
listing — removes the per-vacancy detail request entirely.

Background and measurements: ``docs/research/2026-09-23-parsing-stack.md``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import httpx
from pydantic import ValidationError

from talentflow.models import Vacancy

logger = logging.getLogger(__name__)

SOURCE = "djinni"
LISTING_URL = "https://djinni.co/jobs/"

#: Honest user agent with a contact address, as required by the access rules in
#: ``robots.txt`` etiquette. Replace the URL with a mailto: before production.
USER_AGENT = "TalentFlowBot/0.1 (+https://github.com/FreeAiHub/talentflow-agent)"

#: ``robots.txt`` allows ``/jobs/`` and disallows ``/jobs2``, ``/q``,
#: ``/developers``, ``/free-jobs``, ``/set_lang``. We only ever touch the first.
LD_JSON_PATTERN = re.compile(r"<script[^>]*application/ld\+json[^>]*>(.*?)</script>", re.DOTALL)

# Politeness budget. One listing page yields ~15 vacancies, so a 1s pause costs
# almost nothing while keeping us far below any rate limit.
MIN_REQUEST_DELAY = 1.0
MAX_CONNECTIONS = 2
REQUEST_TIMEOUT = 30.0
MAX_ATTEMPTS = 3
BACKOFF_BASE = 2.0


class DjinniRateLimited(RuntimeError):
    """Djinni answered HTTP 429.

    Raised instead of retrying blindly: hammering a site that just asked us to
    slow down is how a parser gets an IP banned.
    """


def extract_job_postings(html: str) -> list[dict[str, Any]]:
    """Return the raw ``JobPosting`` dicts embedded in a listing page.

    Tolerates a malformed block: a page we cannot parse yields fewer postings
    rather than an exception.
    """
    postings: list[dict[str, Any]] = []
    for block in LD_JSON_PATTERN.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            logger.warning("Skipping unparsable ld+json block (%d chars)", len(block))
            continue

        # The top level is normally a list, but a single object is valid too.
        items = data if isinstance(data, list) else [data]
        postings.extend(
            item for item in items if isinstance(item, dict) and item.get("@type") == "JobPosting"
        )
    return postings


def _clean(value: Any) -> str:
    """Return a stripped string, or ``""`` for anything that is not text."""
    return value.strip() if isinstance(value, str) else ""


def _identifier(raw: Mapping[str, Any]) -> str | None:
    """Extract the vacancy id.

    Djinni currently sends a bare integer, but schema.org also permits a
    ``PropertyValue`` object; both shapes are accepted.
    """
    value = raw.get("identifier")
    if isinstance(value, Mapping):
        value = value.get("value")
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    return text or None


def _company(raw: Mapping[str, Any]) -> str:
    organization = raw.get("hiringOrganization")
    if isinstance(organization, Mapping):
        return _clean(organization.get("name"))
    return ""


def _posted_at(raw: Mapping[str, Any]) -> datetime | None:
    value = _clean(raw.get("datePosted"))
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        logger.warning("Unparsable datePosted: %r", value)
        return None


def to_vacancy(raw: Mapping[str, Any]) -> Vacancy | None:
    """Map one ``JobPosting`` to a :class:`Vacancy`.

    Returns ``None`` for a posting we cannot use, so that one bad record never
    aborts a run of hundreds.
    """
    vacancy_id = _identifier(raw)
    title = _clean(raw.get("title"))
    if not vacancy_id or not title:
        logger.warning("Skipping posting: id=%r title=%r", vacancy_id, title or raw.get("title"))
        return None

    # Built as a mapping so Pydantic does the coercion (str -> HttpUrl, str ->
    # datetime) and rejects anything malformed, rather than mypy having to
    # accept raw strings for typed fields.
    data: dict[str, Any] = {
        "id": vacancy_id,
        "title": title,
        "company": _company(raw),
        "url": _clean(raw.get("url")) or None,
        "source": SOURCE,
        "description": _clean(raw.get("description")),
        "posted_at": _posted_at(raw),
    }

    try:
        return Vacancy.model_validate(data)
    except ValidationError as exc:
        logger.warning("Skipping vacancy %s: %s", vacancy_id, exc)
        return None


class DjinniParser:
    """Collect vacancies from Djinni listing pages.

    Pages are walked in order until ``limit`` unique vacancies are gathered.
    Deduplication is by vacancy id, which Djinni already puts in the URL.
    """

    def __init__(
        self,
        *,
        limit: int = 50,
        client: httpx.AsyncClient | None = None,
        request_delay: float = MIN_REQUEST_DELAY,
        backoff_base: float = BACKOFF_BASE,
    ) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if request_delay < 0:
            raise ValueError("request_delay must not be negative")
        if backoff_base < 0:
            raise ValueError("backoff_base must not be negative")
        self.limit = limit
        self._client = client
        self._request_delay = request_delay
        self._backoff_base = backoff_base

    async def collect(self) -> list[Vacancy]:
        """Fetch listing pages until ``limit`` unique vacancies are collected."""
        collected: dict[str, Vacancy] = {}

        async with self._client_context() as client:
            page = 1
            while len(collected) < self.limit:
                html = await self._fetch_page(client, page)
                if html is None:
                    logger.error("Stopping at page %d: could not fetch", page)
                    break

                added = self._absorb(html, collected)
                if added == 0:
                    logger.info("Page %d added nothing new, stopping", page)
                    break
                page += 1

        return list(collected.values())

    def _absorb(self, html: str, collected: dict[str, Vacancy]) -> int:
        """Add new vacancies from one page; return how many were added."""
        added = 0
        for raw in extract_job_postings(html):
            vacancy = to_vacancy(raw)
            if vacancy is None or vacancy.id in collected:
                continue
            collected[vacancy.id] = vacancy
            added += 1
            if len(collected) >= self.limit:
                break
        return added

    @asynccontextmanager
    async def _client_context(self) -> AsyncIterator[httpx.AsyncClient]:
        """Reuse an injected client, or own a short-lived one."""
        if self._client is not None:
            yield self._client
            return

        limits = httpx.Limits(
            max_connections=MAX_CONNECTIONS,
            max_keepalive_connections=MAX_CONNECTIONS,
        )
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            limits=limits,
            follow_redirects=True,
        ) as client:
            yield client

    async def _fetch_page(self, client: httpx.AsyncClient, page: int) -> str | None:
        """Fetch one listing page, retrying transient failures.

        Returns ``None`` when the page could not be fetched. Raises
        :class:`DjinniRateLimited` on HTTP 429 without retrying.
        """
        params = {"page": page} if page > 1 else None

        for attempt in range(1, MAX_ATTEMPTS + 1):
            if self._request_delay:
                await asyncio.sleep(self._request_delay)
            try:
                response = await client.get(LISTING_URL, params=params)
            except httpx.HTTPError as exc:
                logger.warning(
                    "Page %d, attempt %d/%d failed: %s",
                    page,
                    attempt,
                    MAX_ATTEMPTS,
                    exc,
                )
                await self._backoff(attempt)
                continue

            if response.status_code == httpx.codes.TOO_MANY_REQUESTS:
                raise DjinniRateLimited(
                    f"Djinni answered 429 on page {page}. "
                    "Back off and lower the request rate before retrying."
                )
            if response.is_client_error or response.is_server_error:
                logger.warning(
                    "Page %d, attempt %d/%d: HTTP %d",
                    page,
                    attempt,
                    MAX_ATTEMPTS,
                    response.status_code,
                )
                await self._backoff(attempt)
                continue

            return response.text

        return None

    async def _backoff(self, attempt: int) -> None:
        """Exponential backoff with jitter, to avoid synchronised retries."""
        await asyncio.sleep(self._backoff_base**attempt + random.uniform(0, 1))
