"""Command line entry point: ``uv run python -m talentflow.parsers``.

Collects vacancies from a job board and stores the new ones in the database.
Re-running is idempotent: vacancies that are already stored are not duplicated.

Example::

    uv run python -m talentflow.parsers --source djinni --limit 50
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from talentflow.config import get_settings
from talentflow.models import Vacancy
from talentflow.parsers.djinni import DjinniParser
from talentflow.storage import create_engine, create_sessionmaker, save_vacancies

#: Registry of available sources. Adding a source means adding an entry here.
SOURCES: dict[str, type[DjinniParser]] = {"djinni": DjinniParser}

DEFAULT_LIMIT = 50


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m talentflow.parsers",
        description="Collect vacancies from job boards into TalentFlow.",
    )
    parser.add_argument(
        "--source",
        default="djinni",
        help=f"job board to collect from (available: {', '.join(sorted(SOURCES))})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"maximum number of vacancies to collect (default: {DEFAULT_LIMIT})",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="only print results, suppress progress logging",
    )
    return parser


def _print(vacancy: Vacancy) -> None:
    company = vacancy.company or "—"
    print(f"{vacancy.id}\t{company}\t{vacancy.title}\t{vacancy.url or ''}")


async def run(source: str, limit: int) -> int:
    """Collect vacancies from ``source``, store the new ones, and print them."""
    parser_cls = SOURCES.get(source)
    if parser_cls is None:
        print(
            f"Unknown source {source!r}. Available: {', '.join(sorted(SOURCES))}",
            file=sys.stderr,
        )
        return 2

    vacancies = await parser_cls(limit=limit).collect()

    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_sessionmaker(engine)
    try:
        async with factory() as session:
            saved = await save_vacancies(session, vacancies)
    finally:
        await engine.dispose()

    for vacancy in vacancies:
        _print(vacancy)
    print(f"\n{len(vacancies)} vacancies collected, {saved} saved", file=sys.stderr)
    return 0


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
    return asyncio.run(run(args.source, args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
