"""Background scheduler.

Runs the pipeline on an interval inside the application process. That is enough
for one server and one worker, and avoids standing up Redis and a task queue for
a job that runs twice an hour.

Two constraints worth knowing, both handled or documented rather than hidden:

- **Overlapping runs.** ``max_instances=1`` plus ``coalesce=True`` means a run
  that overruns its interval is not started a second time, and missed runs
  collapse into one instead of piling up.
- **Multiple workers.** Every process would run its own scheduler, so the
  interval must be served by exactly one worker. Deploy with a single uvicorn
  worker, or run the scheduler in a separate process and leave the API without
  it. The pipeline itself is idempotent, so a duplicate run wastes work but
  corrupts nothing.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from talentflow.config import Settings, get_settings
from talentflow.pipeline import run_pipeline
from talentflow.storage import create_sessionmaker, get_engine

logger = logging.getLogger(__name__)

JOB_ID = "talentflow-pipeline"

_scheduler: AsyncIOScheduler | None = None


async def run_scheduled_pipeline(settings: Settings | None = None) -> str:
    """One scheduled execution, with its own database session."""
    settings = settings or get_settings()
    factory = create_sessionmaker(get_engine())

    async with factory() as session:
        result = await run_pipeline(session, settings=settings)

    if not result.ok:
        failed = [s for s in result.stages if s.status == "failed"]
        logger.error(
            "Scheduled pipeline reported failures: %s",
            "; ".join(f"{s.stage}: {s.error}" for s in failed),
        )
    return result.summary()


def build_scheduler(settings: Settings | None = None) -> AsyncIOScheduler:
    """Create the scheduler with the pipeline job registered."""
    settings = settings or get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_scheduled_pipeline,
        trigger=IntervalTrigger(minutes=settings.scheduler_interval_minutes),
        id=JOB_ID,
        name="collect, score and draft",
        # Never start a second run while the first is still going, and collapse
        # a backlog of missed runs into one.
        max_instances=1,
        coalesce=True,
        # Let a run finish rather than killing it mid-write on shutdown.
        misfire_grace_time=settings.scheduler_interval_minutes * 60,
        replace_existing=True,
    )
    return scheduler


def start_scheduler(settings: Settings | None = None) -> AsyncIOScheduler | None:
    """Start the scheduler if it is enabled. Returns ``None`` when it is not."""
    global _scheduler

    settings = settings or get_settings()
    if not settings.scheduler_enabled:
        logger.info(
            "Scheduler disabled (TALENTFLOW_SCHEDULER_ENABLED=false); "
            "the pipeline will only run when invoked."
        )
        return None

    if _scheduler is not None:
        return _scheduler

    _scheduler = build_scheduler(settings)
    _scheduler.start()
    logger.info("Scheduler started: pipeline every %d minutes", settings.scheduler_interval_minutes)
    return _scheduler


def stop_scheduler() -> None:
    """Stop the scheduler if it is running."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
        _scheduler = None


def get_scheduler() -> AsyncIOScheduler | None:
    """The running scheduler, or ``None``."""
    return _scheduler
