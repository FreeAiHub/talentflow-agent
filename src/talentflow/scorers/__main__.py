"""Command line entry point: ``uv run python -m talentflow.scorers``.

Scores stored vacancies that do not have a score yet and saves the results.

Example::

    uv run python -m talentflow.scorers --limit 20
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from talentflow.config import get_settings
from talentflow.llm.client import LLMClient
from talentflow.llm.errors import LlmError
from talentflow.scorers.quality_scorer import DEFAULT_MIN_SCORE, QualityScorer
from talentflow.storage import create_engine, create_sessionmaker, list_vacancies, save_score

DEFAULT_LIMIT = 20


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m talentflow.scorers",
        description="Score stored vacancies against the ideal-customer profile.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"how many to score (default {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help=f"reporting threshold (default {DEFAULT_MIN_SCORE})",
    )
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    return parser


async def run(limit: int, min_score: float, quiet: bool) -> int:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_sessionmaker(engine)

    try:
        async with factory() as session:
            vacancies = await list_vacancies(session, limit=limit)
            unscored = [v for v in vacancies if not v.reasons]

            if not unscored:
                print("No vacancies to score. Run the parser first.", file=sys.stderr)
                return 0

            print(f"Scoring {len(unscored)} vacancies...", file=sys.stderr)

            scorer = QualityScorer(
                LLMClient(session, settings=settings, purpose="score"),
                min_score=min_score,
                settings=settings,
            )

            try:
                outcomes = await scorer.score_many(unscored)
            except LlmError as exc:
                print(f"Scoring failed: {exc}", file=sys.stderr)
                return 1

            for outcome in outcomes:
                await save_score(
                    session,
                    outcome.vacancy.id,
                    score=outcome.score,
                    reasons=outcome.vacancy.reasons,
                    model=outcome.model,
                )
                if not quiet:
                    flag = "+" if outcome.score >= min_score else " "
                    cached = " (cached)" if outcome.cached else ""
                    print(
                        f"{flag} {outcome.score:.2f}  {outcome.vacancy.company[:20]:20} "
                        f"{outcome.vacancy.title[:44]}{cached}"
                    )

            above = sum(1 for o in outcomes if o.score >= min_score)
            tokens_in = sum(o.tokens_in for o in outcomes)
            tokens_out = sum(o.tokens_out for o in outcomes)
            print(
                f"\nScored {len(outcomes)} | above {min_score}: {above} | "
                f"tokens in/out: {tokens_in}/{tokens_out}",
                file=sys.stderr,
            )
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
