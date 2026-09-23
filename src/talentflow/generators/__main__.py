"""Command line entry point: ``uv run python -m talentflow.generators``.

Generates outreach drafts for the highest-scoring vacancies that do not have
one yet, and stores each as pending. **Nothing is sent** — a draft waits for a
human decision.

Example::

    uv run python -m talentflow.generators --limit 5 --min-score 0.7
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from talentflow.config import get_settings
from talentflow.generators.response import ResponseGenerator
from talentflow.llm.client import LLMClient
from talentflow.llm.errors import LlmError
from talentflow.storage import (
    create_draft_application,
    create_engine,
    create_sessionmaker,
    list_applications,
    list_vacancies,
)

DEFAULT_LIMIT = 5
DEFAULT_MIN_SCORE = 0.7


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m talentflow.generators",
        description="Draft outreach for scored vacancies. Nothing is sent.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"how many drafts (default {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help=f"only vacancies at or above this score (default {DEFAULT_MIN_SCORE})",
    )
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    return parser


async def run(limit: int, min_score: float, quiet: bool) -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_sessionmaker(engine)

    try:
        async with factory() as session:
            candidates = await list_vacancies(session, min_score=min_score, limit=limit * 4)
            existing = await list_applications(session, limit=1000)
            already = {row.vacancy_id for row in existing}
            todo = [v for v in candidates if v.id not in already][:limit]

            if not todo:
                print(
                    f"No vacancies at or above {min_score} need a draft. Score vacancies first.",
                    file=sys.stderr,
                )
                return 0

            auto_approve = not settings.human_in_the_loop
            if auto_approve:
                print(
                    "WARNING: TALENTFLOW_HUMAN_IN_THE_LOOP is false — drafts will be "
                    "marked approved without review. A failed grounding check is still "
                    "never approved.",
                    file=sys.stderr,
                )

            print(f"Drafting outreach for {len(todo)} vacancies...", file=sys.stderr)

            generator = ResponseGenerator(
                LLMClient(session, settings=settings, purpose="generate"),
                settings=settings,
            )

            drafted = 0
            blocked = 0
            for vacancy in todo:
                try:
                    outcome = await generator.generate(vacancy)
                except LlmError as exc:
                    print(f"  {vacancy.id}: failed — {exc}", file=sys.stderr)
                    continue

                application = await create_draft_application(
                    session,
                    vacancy.id,
                    outcome.draft.response_text,
                    sendable=outcome.is_sendable,
                    auto_approve=auto_approve,
                )
                drafted += 1
                if not outcome.is_sendable:
                    blocked += 1

                if not quiet:
                    mark = " " if outcome.is_sendable else "!"
                    print(
                        f"{mark} #{application.id}  {vacancy.company[:20]:20} "
                        f"{vacancy.title[:40]}  {outcome.draft.word_count}w"
                    )
                    if not outcome.is_sendable and outcome.grounding:
                        for issue in outcome.grounding.unsupported[:2]:
                            print(f"      выдумано: {issue.claim[:70]}")

            print(
                f"\nDrafted {drafted} | awaiting review: {drafted - blocked} | "
                f"blocked by grounding: {blocked}",
                file=sys.stderr,
            )
            if blocked:
                print(
                    "Drafts marked '!' contain claims the vacancy text does not support "
                    "and cannot be approved.",
                    file=sys.stderr,
                )
            print("Nothing was sent. Review with GET /api/v1/applications.", file=sys.stderr)
        return 0
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    if args.limit <= 0:
        print("--limit must be positive", file=sys.stderr)
        return 2
    return asyncio.run(run(args.limit, args.min_score, args.quiet))


if __name__ == "__main__":
    raise SystemExit(main())
