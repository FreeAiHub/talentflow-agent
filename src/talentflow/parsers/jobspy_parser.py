"""JobSpy parser adapter (stub).

MVP Day 2: wrap https://github.com/cullenwatson/JobSpy to collect
vacancies from Djinni, Work.ua, LinkedIn and Indeed into Vacancy models.
"""

from talentflow.models import Vacancy


class JobSpyParser:
    sources = ("djinni", "work_ua", "linkedin", "indeed")

    def __init__(self, query: str = "python developer", limit: int = 50) -> None:
        self.query = query
        self.limit = limit

    def collect(self) -> list[Vacancy]:
        """Fetch vacancies from all sources (implemented on Day 2)."""
        raise NotImplementedError("JobSpy adapter lands on MVP Day 2 (INTEGRATIONS.md)")
