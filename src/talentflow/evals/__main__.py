"""Run the scoring evaluation.

    uv run python -m talentflow.evals
    uv run python -m talentflow.evals --min-precision 0.9
    uv run python -m talentflow.evals --write-baseline          # обновить docs/EVAL-BASELINE.md
    uv run python -m talentflow.evals --from-file scores.json   # без базы

Reads the labelled vacancies from ``tests/fixtures/labeled_vacancies.json`` and
the scores from the database. Vacancies the fixture labels but the database has
not scored are reported, not silently skipped: an evaluation over half the sample
is not the evaluation it claims to be.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from talentflow.config import get_settings
from talentflow.evals import Metrics, pick_threshold, summarise, sweep
from talentflow.storage import create_engine, create_sessionmaker, list_vacancies

FIXTURE = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "labeled_vacancies.json"
BASELINE = Path(__file__).resolve().parents[3] / "docs" / "EVAL-BASELINE.md"


def load_labels(path: Path) -> tuple[dict[str, bool], dict[str, Any]]:
    """Return ``{vacancy_id: relevant}`` and the fixture's metadata."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels = {v["id"]: bool(v["relevant"]) for v in payload["vacancies"]}
    return labels, payload.get("_meta", {})


async def scores_from_database(ids: set[str]) -> dict[str, float]:
    """Collect scores for the labelled vacancies."""
    engine = create_engine(get_settings().database_url)
    factory = create_sessionmaker(engine)
    try:
        async with factory() as session:
            # Scored-only listing: the threshold is what we are choosing, so no
            # threshold is applied here.
            vacancies = await list_vacancies(session, limit=10_000)
    finally:
        await engine.dispose()

    return {v.id: v.score for v in vacancies if v.id in ids and v.reasons}


def report(
    metrics: list[Metrics], chosen: Metrics | None, meta: dict[str, Any], scored: int, total: int
) -> str:
    lines = [
        "# Оценка качества скоринга",
        "",
        f"Размеченных вакансий: **{total}**, оценено: **{scored}**.",
        "",
    ]

    if meta.get("requires_human_confirmation"):
        lines += [
            "> ⚠️ **Разметка предварительная.** Её сделал агент, и он же писал промпт",
            "> скоринга — по методике это смещение в пользу автора. Метрика измеряет",
            "> согласие с собой, а не объективную релевантность. Перед решением по",
            "> этим числам разметку должен подтвердить или переделать человек.",
            "",
        ]

    if scored < total:
        lines += [
            f"> ⚠️ Оценено {scored} из {total}. Метрики ниже посчитаны только по",
            "> оценённым. Это не та выборка, на которую рассчитывали.",
            "",
        ]

    lines += [summarise(metrics), ""]

    if chosen is None:
        lines += [
            "**Порог не выбран:** ни один не проходит по precision. Это результат,",
            "> а не ошибка — значит скоринг пока не отделяет хорошие лиды от плохих.",
        ]
    else:
        lines += [
            f"**Рекомендованный порог: {chosen.threshold:.1f}** — "
            f"precision {chosen.precision}, recall {chosen.recall}.",
            "",
            chosen.accuracy_note,
        ]

    return "\n".join(lines)


async def run(args: argparse.Namespace) -> int:
    labels, meta = load_labels(args.fixture)
    total = len(labels)

    if args.from_file:
        raw = json.loads(Path(args.from_file).read_text(encoding="utf-8"))
        scores = {k: float(v) for k, v in raw.items() if k in labels}
    else:
        scores = await scores_from_database(set(labels))
        if not scores:
            print(
                "В базе нет оценённых размеченных вакансий.\n"
                "Сначала прогоните скоринг:\n"
                "  uv run python -m talentflow.scorers --limit 30\n"
                "\nЛибо передайте оценки файлом: --from-file scores.json",
                file=sys.stderr,
            )
            return 1

    common = sorted(scores)
    score_list = [scores[i] for i in common]
    label_list = [labels[i] for i in common]

    metrics = sweep(score_list, label_list, thresholds=args.thresholds)
    chosen = pick_threshold(metrics, min_precision=args.min_precision)
    text = report(metrics, chosen, meta, scored=len(common), total=total)

    print(text)

    if args.write_baseline:
        BASELINE.write_text(text + "\n", encoding="utf-8")
        print(f"\nЗаписано: {BASELINE}", file=sys.stderr)

    missing = sorted(set(labels) - set(common))
    if missing and not args.quiet:
        print(f"\nБез оценки ({len(missing)}): {', '.join(missing)}", file=sys.stderr)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Оценка качества скоринга вакансий")
    parser.add_argument("--fixture", type=Path, default=FIXTURE)
    parser.add_argument("--from-file", type=Path, help="оценки в JSON вместо базы")
    parser.add_argument(
        "--thresholds",
        type=float,
        nargs="+",
        default=None,
        help="пороги для перебора (по умолчанию 0.1 … 0.9)",
    )
    parser.add_argument(
        "--min-precision",
        type=float,
        default=0.8,
        help="пол, ниже которого порог не рассматривается (по умолчанию 0.8)",
    )
    parser.add_argument("--write-baseline", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return asyncio.run(run(parser.parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
