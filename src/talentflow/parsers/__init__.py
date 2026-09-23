"""Vacancy parsers.

Each source gets its own module and exposes a parser class with an async
``collect()`` returning :class:`~talentflow.models.Vacancy` objects.

Currently implemented: :class:`~talentflow.parsers.djinni.DjinniParser`.
JobSpy (LinkedIn, Indeed) is deferred to phase 2 — note that JobSpy does *not*
support Djinni or Work.ua, which is why Djinni has its own parser.
"""

from talentflow.parsers.djinni import DjinniParser, extract_job_postings, to_vacancy

__all__ = ["DjinniParser", "extract_job_postings", "to_vacancy"]
