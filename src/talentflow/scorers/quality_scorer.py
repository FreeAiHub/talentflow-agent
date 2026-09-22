"""Quality scorer (stub).

MVP Day 2: LLM-backed scoring via prompts/quality_scorer.md and
prompts/archetype_matcher.md, validated against ScoredVacancy schema.
"""

from talentflow.models import Vacancy


class QualityScorer:
    def __init__(self, min_score: float = 0.6) -> None:
        self.min_score = min_score

    def score(self, vacancy: Vacancy) -> float:
        """Return relevance in [0, 1] (LLM-backed implementation lands on Day 2)."""
        raise NotImplementedError("Scorer lands on MVP Day 2 (INTEGRATIONS.md)")
