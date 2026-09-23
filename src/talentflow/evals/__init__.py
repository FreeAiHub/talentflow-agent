"""Scoring evaluation: does the score actually separate good leads from bad?

:mod:`talentflow.evals.metrics` holds the statistics. This package is the only
place that knows about labels, and it deliberately does not know how scores were
produced — the same harness measures an LLM scorer, a Jev scorer, or a
hand-written rule.
"""

from talentflow.evals.metrics import (
    Confusion,
    Interval,
    Metrics,
    confusion_at,
    evaluate,
    pick_threshold,
    summarise,
    sweep,
    wilson_interval,
)

__all__ = [
    "Confusion",
    "Interval",
    "Metrics",
    "confusion_at",
    "evaluate",
    "pick_threshold",
    "summarise",
    "sweep",
    "wilson_interval",
]
