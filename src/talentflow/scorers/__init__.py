"""Vacancy scoring.

:class:`~talentflow.scorers.quality_scorer.QualityScorer` judges whether a
vacancy is worth pursuing as a lead, using the prompt in
``prompts/vacancy_scorer.md``.
"""

from talentflow.scorers.quality_scorer import (
    DEFAULT_MIN_SCORE,
    QualityScorer,
    ScoreOutcome,
    ScoringPayload,
    ScoringSignals,
    parse_payload,
)

__all__ = [
    "DEFAULT_MIN_SCORE",
    "QualityScorer",
    "ScoreOutcome",
    "ScoringPayload",
    "ScoringSignals",
    "parse_payload",
]
