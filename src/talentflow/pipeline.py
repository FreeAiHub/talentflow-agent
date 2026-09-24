"""The pipeline: parse vacancies, score them, optionally draft outreach.

Each stage is independent and recorded in the ``runs`` table. A stage that
cannot run — the LLM budget is spent, no API key is configured, drafting is
switched off — is marked ``skipped`` with the reason, and the remaining stages
still run. Parsing does not need an LLM, so a spent budget must not stop it.

Re-running is safe and cheap: collected vacancies are deduplicated by source id,
scoring is skipped for vacancies that already have a score, and identical
prompts are served from cache rather than paid for twice.
"""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from talentflow.config import Settings, get_settings
from talentflow.llm.client import LLMClient
from talentflow.llm.errors import LlmBudgetExceeded, LlmError, NoProviderConfigured
from talentflow.notifiers import TelegramError, TelegramNotConfigured, TelegramNotifier, format_lead
from talentflow.parsers.djinni import DjinniParser
from talentflow.scorers import QualityScorer
from talentflow.storage import (
    count_vacancies,
    create_draft_application,
    create_engine,
    create_sessionmaker,
    finish_run,
    get_vacancy,
    list_applications,
    list_unnotified_applications,
    list_vacancies,
    mark_notified,
    save_score,
    save_vacancies,
    start_run,
)

logger = logging.getLogger(__name__)

StageStatus = Literal["ok", "failed", "skipped"]


@dataclass
class StageResult:
    """What happened during one stage of a run."""

    stage: str
    status: StageStatus
    items: int = 0
    error: str | None = None
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.status == "ok"


@dataclass
class PipelineResult:
    """The outcome of a full run."""

    stages: list[StageResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no stage failed. Skips are not failures."""
        return all(stage.status != "failed" for stage in self.stages)

    @property
    def collected(self) -> int:
        return sum(s.items for s in self.stages if s.stage == "parse")

    @property
    def scored(self) -> int:
        return sum(s.items for s in self.stages if s.stage == "score")

    @property
    def drafted(self) -> int:
        return sum(s.items for s in self.stages if s.stage == "generate")

    @property
    def notified(self) -> int:
        return sum(s.items for s in self.stages if s.stage == "notify")

    def summary(self) -> str:
        parts = [
            f"{stage.stage}={stage.status}" + (f"({stage.items})" if stage.status == "ok" else "")
            for stage in self.stages
        ]
        return " | ".join(parts)


async def _recorded(
    session: AsyncSession,
    kind: str,
    action: Callable[[], Awaitable[int]],
) -> StageResult:
    """Run one stage, recording it in ``runs`` whatever happens.

    Returns a :class:`StageResult` instead of raising: one broken stage must not
    abandon the ones after it.
    """
    run = await start_run(session, kind)
    started = time.monotonic()

    def elapsed() -> int:
        return int((time.monotonic() - started) * 1000)

    try:
        items = await action()
    except LlmBudgetExceeded as exc:
        # A spent budget is an expected condition, not a fault.
        await finish_run(session, run.id, status="skipped", error=str(exc))
        logger.warning("Stage %s skipped: %s", kind, exc)
        return StageResult(kind, "skipped", error=str(exc), duration_ms=elapsed())
    except (NoProviderConfigured, TelegramNotConfigured) as exc:
        # Also expected while a credential is missing, and it would repeat on
        # every run — recorded as a skip with the reason attached.
        await finish_run(session, run.id, status="skipped", error=str(exc))
        logger.warning("Stage %s skipped: %s", kind, exc)
        return StageResult(kind, "skipped", error=str(exc), duration_ms=elapsed())
    except (LlmError, TelegramError) as exc:
        await finish_run(session, run.id, status="failed", error=str(exc))
        logger.error("Stage %s failed: %s", kind, exc)
        return StageResult(kind, "failed", error=str(exc), duration_ms=elapsed())
    except Exception as exc:  # noqa: BLE001 - one stage must not kill the run
        await finish_run(session, run.id, status="failed", error=str(exc))
        logger.exception("Stage %s crashed", kind)
        return StageResult(kind, "failed", error=str(exc), duration_ms=elapsed())

    await finish_run(session, run.id, status="ok", items_processed=items)
    logger.info("Stage %s ok: %d items in %dms", kind, items, elapsed())
    return StageResult(kind, "ok", items=items, duration_ms=elapsed())


async def run_parse(session: AsyncSession, settings: Settings, *, limit: int | None = None) -> int:
    """Collect vacancies from Djinni and store the new ones."""
    parser = DjinniParser(limit=limit or settings.pipeline_parse_limit)
    vacancies = await parser.collect()
    return await save_vacancies(session, vacancies)


async def run_score(session: AsyncSession, settings: Settings, *, limit: int | None = None) -> int:
    """Score stored vacancies that do not have a score yet."""
    candidates = await list_vacancies(session, limit=limit or settings.pipeline_score_limit)
    unscored = [v for v in candidates if not v.reasons]
    if not unscored:
        return 0

    scorer = QualityScorer(
        LLMClient(session, settings=settings, purpose="score"),
        min_score=settings.min_lead_score,
        settings=settings,
    )
    outcomes = await scorer.score_many(unscored)
    for outcome in outcomes:
        await save_score(
            session,
            outcome.vacancy.id,
            score=outcome.score,
            reasons=outcome.vacancy.reasons,
            model=outcome.model,
        )
    return len(outcomes)


async def run_generate(
    session: AsyncSession, settings: Settings, *, limit: int | None = None
) -> int:
    """Draft outreach for the best vacancies that do not have a draft yet."""
    from talentflow.generators import ResponseGenerator

    wanted = limit if limit is not None else settings.pipeline_generate_limit
    if wanted <= 0:
        return 0

    candidates = await list_vacancies(session, min_score=settings.min_lead_score, limit=wanted * 4)
    existing = await list_applications(session, limit=1000)
    already = {row.vacancy_id for row in existing}
    todo = [v for v in candidates if v.id not in already][:wanted]
    if not todo:
        return 0

    if settings.sender_profile_is_placeholder:
        logger.warning(
            "Sender profile is still the shipped placeholder: the generator has no "
            "verifiable experience to cite, so every draft will be blocked by the "
            "grounding check. Set TALENTFLOW_SENDER_PROFILE to draft anything sendable."
        )

    generator = ResponseGenerator(
        LLMClient(session, settings=settings, purpose="generate"), settings=settings
    )
    drafted = 0
    for vacancy in todo:
        try:
            outcome = await generator.generate(vacancy)
        except LlmError as exc:
            logger.warning("Drafting failed for %s: %s", vacancy.id, exc)
            continue
        await create_draft_application(
            session,
            vacancy.id,
            outcome.draft.response_text,
            sendable=outcome.is_sendable,
            auto_approve=not settings.human_in_the_loop and outcome.is_sendable,
        )
        drafted += 1
    return drafted


async def run_notify(session: AsyncSession, settings: Settings, *, limit: int = 20) -> int:
    """Tell the reviewer about pending drafts they have not seen yet.

    A draft is marked notified only after the message is actually sent, so a
    failed send is retried on the next run rather than silently dropped.
    """
    notifier = TelegramNotifier(settings)
    if not notifier.enabled:
        raise TelegramNotConfigured(
            "Telegram is not configured: set TALENTFLOW_TELEGRAM_BOT_TOKEN "
            "and TALENTFLOW_TELEGRAM_CHAT_ID"
        )

    pending = await list_unnotified_applications(session, limit=limit)
    sent = 0
    for application in pending:
        vacancy = await get_vacancy(session, application.vacancy_id)
        if vacancy is None:
            logger.warning(
                "Application %d references missing vacancy %s",
                application.id,
                application.vacancy_id,
            )
            continue

        notification = format_lead(
            application_id=application.id,
            title=vacancy.title,
            company=vacancy.company,
            score=vacancy.score,
            reasons=vacancy.reasons,
            url=str(vacancy.url) if vacancy.url else None,
            draft=application.text,
        )
        try:
            await notifier.send_lead(notification)
        except TelegramError as exc:
            logger.warning("Could not notify about application %d: %s", application.id, exc)
            continue

        await mark_notified(session, application.id)
        sent += 1
    return sent


async def run_pipeline(
    session: AsyncSession,
    *,
    settings: Settings | None = None,
    parse_limit: int | None = None,
    score_limit: int | None = None,
    generate_limit: int | None = None,
) -> PipelineResult:
    """Run parse, then score, then optional drafting, recording each stage."""
    settings = settings or get_settings()
    result = PipelineResult()

    result.stages.append(
        await _recorded(session, "parse", lambda: run_parse(session, settings, limit=parse_limit))
    )
    result.stages.append(
        await _recorded(session, "score", lambda: run_score(session, settings, limit=score_limit))
    )

    if generate_limit is not None or settings.pipeline_generate_limit > 0:
        result.stages.append(
            await _recorded(
                session,
                "generate",
                lambda: run_generate(session, settings, limit=generate_limit),
            )
        )

    result.stages.append(await _recorded(session, "notify", lambda: run_notify(session, settings)))

    logger.info("Pipeline finished: %s", result.summary())
    return result


# --- CLI -------------------------------------------------------------------


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m talentflow.pipeline",
        description="Run the collection and scoring pipeline once.",
    )
    parser.add_argument("--parse-limit", type=int, default=None, help="vacancies to collect")
    parser.add_argument("--score-limit", type=int, default=None, help="vacancies to score")
    parser.add_argument(
        "--generate-limit",
        type=int,
        default=None,
        help="drafts to write (0 disables drafting)",
    )
    return parser


async def _main(args: argparse.Namespace) -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_sessionmaker(engine)
    try:
        async with factory() as session:
            result = await run_pipeline(
                session,
                settings=settings,
                parse_limit=args.parse_limit,
                score_limit=args.score_limit,
                generate_limit=args.generate_limit,
            )
            total = await count_vacancies(session)
        print(result.summary())
        print(f"vacancies in database: {total}")
        for stage in result.stages:
            if stage.status == "skipped":
                print(f"  {stage.stage} skipped: {stage.error}")
            elif stage.status == "failed":
                print(f"  {stage.stage} FAILED: {stage.error}")
        return 0 if result.ok else 1
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    return asyncio.run(_main(build_arg_parser().parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
