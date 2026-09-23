#!/usr/bin/env python
"""End-to-end demo: from an empty database to an approved outreach draft.

    uv run python scripts/demo.py            # offline, uses the recorded page
    uv run python scripts/demo.py --live     # pulls fresh vacancies from Djinni

The offline run touches no network at all: it reads the recorded Djinni page in
``tests/fixtures`` and answers as a **stub model**. That makes it deterministic
and free, and it is what CI could run. It also means the offline run proves the
plumbing, not the model — the output says so rather than implying otherwise.

A live run needs a key in ``.env`` and scores real vacancies with a real model.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from talentflow.config import Settings  # noqa: E402
from talentflow.generators import ResponseGenerator  # noqa: E402
from talentflow.llm.client import LLMClient, LlmResult  # noqa: E402
from talentflow.notifiers import format_lead  # noqa: E402
from talentflow.parsers.djinni import extract_job_postings, to_vacancy  # noqa: E402
from talentflow.scorers import QualityScorer  # noqa: E402
from talentflow.storage import (  # noqa: E402
    assert_sendable,
    collect_stats,
    create_draft_application,
    create_engine,
    create_sessionmaker,
    decide_application,
    save_score,
    save_vacancies,
)
from talentflow.storage.tables import Base  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "djinni_jobs_page1.html"

STUB_REASONS = [
    "Прямой работодатель: описывает свою команду и продукт",
    "Стек пересекается с нашими сервисами",
]

STUB_DRAFT = (
    "Hi — вы описываете миграцию на Python-сервисы и хотите провести её без "
    "простоя. Это близко к тому, чем я занимаюсь: разбирал монолит на сервисы "
    "для платежного клиента, переносили по таблицам, без окна обслуживания.\n\n"
    "Если полезно — расскажу, где у нас было больно. Двадцать минут, без "
    "презентации."
)


def heading(step: int, text: str) -> None:
    print(f"\n\033[1m{step}. {text}\033[0m")


class StubClient:
    """Answers as a model would, with a fixed score and a fixed draft.

    Deliberately obvious about being a stub: the point of the offline demo is
    to exercise the plumbing, and pretending otherwise would be worse than
    having no demo.
    """

    def __init__(self) -> None:
        self.calls = 0

    #: Distinctive phrases rather than single keywords: the scoring prompt also
    #: contains the word "grounding", so matching on that alone dispatched every
    #: request to the wrong branch.
    MARKERS = (
        ("You are a fact-checker", "grounding"),
        ("Write a short outreach message", "draft"),
        ("Scoring rubric", "score"),
    )

    @classmethod
    def _kind(cls, prompt: str) -> str:
        for marker, kind in cls.MARKERS:
            if marker in prompt:
                return kind
        raise RuntimeError(
            "demo stub does not recognise this prompt; expected one of "
            f"{[m for m, _ in cls.MARKERS]}"
        )

    async def complete(self, prompt: str, *, system: str | None = None) -> LlmResult:
        self.calls += 1
        kind = self._kind(prompt)
        if kind == "grounding":
            payload: dict[str, Any] = {
                "verdict": "ok",
                "unsupported": [],
                "checked": 3,
                "notes": "",
            }
        elif kind == "draft":
            payload = {
                "response_text": STUB_DRAFT,
                "key_highlights": ["Миграция на Python-сервисы", "Опыт cutover без простоя"],
                "cta": "Reply with a time",
                "tone": "direct",
                "word_count": 0,
                "reasoning": "Отклик на конкретную проблему из вакансии.",
            }
        else:
            payload = {
                "score": 0.82,
                "reasons": STUB_REASONS,
                "signals": {
                    "role_level": "senior",
                    "is_direct_employer": True,
                    "is_agency_resale": False,
                    "unpaid_or_equity": False,
                    "matched_technologies": ["Python"],
                    "location": "remote",
                },
                "unknowns": ["Бюджет не указан"],
                "summary": "STUB",
            }
        return LlmResult(
            text=json.dumps(payload, ensure_ascii=False),
            model="stub-model",
            provider="stub",
            tokens_in=100,
            tokens_out=50,
        )


async def collect_offline(limit: int) -> list[Any]:
    """Read vacancies out of the recorded page — no network."""
    postings = extract_job_postings(FIXTURE.read_text(encoding="utf-8"))
    vacancies = [v for v in (to_vacancy(raw) for raw in postings) if v is not None]
    print(f"   прочитано из записанной страницы: {len(postings)}, валидных: {len(vacancies)}")
    return vacancies[:limit]


async def collect_live(limit: int) -> list[Any]:
    from talentflow.parsers.djinni import DjinniParser

    print(f"   запрашиваю {limit} вакансий у djinni.co...")
    return await DjinniParser(limit=limit).collect()


async def run_demo(limit: int, live: bool, min_score: float) -> int:
    settings = Settings(
        min_lead_score=min_score,
        # Drafting is off in the pipeline by default; the demo drives it directly.
        pipeline_generate_limit=0,
    )

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "demo.db"
        engine = create_engine(f"sqlite+aiosqlite:///{db_path}")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = create_sessionmaker(engine)

        try:
            async with factory() as session:
                heading(1, "Собираем вакансии")
                vacancies = await (collect_live(limit) if live else collect_offline(limit))
                if not vacancies:
                    print("   нечего показывать")
                    return 1
                added = await save_vacancies(session, vacancies)
                print(f"   сохранено новых: {added}")

                heading(2, "Собираем повторно — идемпотентность")
                again = await save_vacancies(session, vacancies)
                print(f"   повторно добавлено: {again} (ожидается 0)")

                heading(3, "Оцениваем")
                client: Any = (
                    LLMClient(session, settings=settings, purpose="score") if live else StubClient()
                )
                scorer = QualityScorer(client, min_score=min_score, settings=settings)
                outcomes = await scorer.score_many(vacancies[: min(limit, 5)])
                for outcome in outcomes:
                    await save_score(
                        session,
                        outcome.vacancy.id,
                        score=outcome.score,
                        reasons=outcome.vacancy.reasons,
                        model=outcome.model,
                    )
                for outcome in outcomes:
                    flag = "✓" if outcome.score >= min_score else " "
                    print(
                        f"   {flag} {outcome.score:.2f}  "
                        f"{outcome.vacancy.company[:22]:22} {outcome.vacancy.title[:38]}"
                    )
                above = [o for o in outcomes if o.score >= min_score]
                print(f"   выше порога {min_score}: {len(above)} из {len(outcomes)}")

                if not above:
                    print("\n   ни одна вакансия не прошла порог — демонстрация завершена")
                    return 0

                heading(4, "Пишем черновик отклика")
                best = above[0].vacancy
                generator = ResponseGenerator(client, settings=settings)
                draft = await generator.generate(best)
                print(f"   вакансия: {best.company} — {best.title}")
                print(f"   слов: {draft.draft.word_count}")
                print(
                    f"   проверка на выдумки: {draft.grounding.verdict if draft.grounding else '—'}"
                )
                print(f"   отправляемо: {'да' if draft.is_sendable else 'НЕТ'}")

                application = await create_draft_application(
                    session, best.id, draft.draft.response_text, sendable=draft.is_sendable
                )
                print(f"   черновик #{application.id}, статус: {application.status}")

                heading(5, "Уведомление, которое уйдёт в Telegram")
                notification = format_lead(
                    application_id=application.id,
                    title=best.title,
                    company=best.company,
                    score=above[0].score,
                    reasons=best.reasons,
                    url=str(best.url) if best.url else None,
                    draft=draft.draft.response_text,
                )
                print("\n".join(f"   │ {line}" for line in notification.text.splitlines()))
                buttons = notification.keyboard()["inline_keyboard"][0]
                print("   │ " + "  ".join(f"[{b['text']}]" for b in buttons))

                heading(6, "Гейт: до подтверждения отправить нельзя")
                try:
                    assert_sendable(application)
                    print("   ОШИБКА: отправка разрешена без подтверждения")
                    return 1
                except Exception as exc:  # noqa: BLE001 - the demo shows the refusal
                    print(f"   отправка запрещена: {str(exc)[:70]}...")

                heading(7, "Человек подтверждает")
                approved = await decide_application(session, application.id, approved=True)
                assert approved is not None
                assert_sendable(approved)
                print(f"   статус: {approved.status}, отправка разрешена")

                heading(8, "Итог")
                stats = await collect_stats(session, min_score=min_score)
                print(f"   собрано вакансий:      {stats.vacancies_total}")
                print(f"   оценено:               {stats.vacancies_scored}")
                print(f"   выше порога:           {stats.vacancies_above_threshold}")
                print(f"   черновиков к разбору:  {stats.applications_pending}")
                print(f"   утверждено:            {stats.applications_approved}")

            if not live:
                print(
                    "\n\033[33mВНИМАНИЕ: оффлайн-прогон. Модель подменена заглушкой с "
                    "фиксированной оценкой.\nПроверена проводка, а не качество модели. "
                    "Для живой проверки: --live и ключ в .env.\033[0m"
                )
            return 0
        finally:
            await engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description="TalentFlow end-to-end demo")
    parser.add_argument("--limit", type=int, default=5, help="vacancies to work with")
    parser.add_argument("--live", action="store_true", help="use the real Djinni and a real model")
    parser.add_argument("--min-score", type=float, default=0.6)
    args = parser.parse_args()
    return asyncio.run(run_demo(args.limit, args.live, args.min_score))


if __name__ == "__main__":
    raise SystemExit(main())
