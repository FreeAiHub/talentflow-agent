"""Outreach generation.

:class:`~talentflow.generators.response.ResponseGenerator` writes a draft and
fact-checks it against the vacancy text. Nothing it produces is sent: a draft is
stored pending and only a human decision moves it.
"""

from talentflow.generators.response import (
    DraftOutcome,
    GeneratedResponse,
    GroundingIssue,
    GroundingReport,
    ResponseGenerator,
    count_words,
    has_placeholder,
    parse_draft,
    parse_grounding,
)

__all__ = [
    "DraftOutcome",
    "GeneratedResponse",
    "GroundingIssue",
    "GroundingReport",
    "ResponseGenerator",
    "count_words",
    "has_placeholder",
    "parse_draft",
    "parse_grounding",
]
