#!/usr/bin/env python
"""Build a model comparison table from the OpenRouter catalogue.

    uv run python scripts/model_catalog.py                 # таблица в stdout
    uv run python scripts/model_catalog.py --json out.json # плюс снимок данных
    uv run python scripts/model_catalog.py --sort value    # по отдаче за деньги
    uv run python scripts/model_catalog.py --has tools     # только те, что умеют инструменты

Why a script and not a one-off scrape: the catalogue changes weekly. Prices move,
models appear and disappear, and a table copied into a document is stale within a
month. Re-running this is one command.

**The API is not the whole catalogue.** `typesafe/jev-1.13` has a live model page
but is absent from `/api/v1/models` (455 entries, `total_count` 455, no
pagination). Anything that must be complete needs cross-checking against the
site — see `--known-missing` below.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

API = "https://openrouter.ai/api/v1/models"

#: Verified models the API does not list. Checked by fetching each model page and
#: reading its content — a 200 status alone proves nothing, because the site
#: returns 200 for a made-up slug too.
KNOWN_MISSING: list[dict[str, Any]] = [
    {
        "id": "typesafe/jev-1.13",
        "name": "TypeSafe: Jev 1.13",
        "context_length": 32_000,
        "pricing": {"prompt": "0.000000042", "completion": "0"},
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        "supported_parameters": ["response_format", "structured_outputs"],
        "benchmarks": {},
        "reasoning": None,
        "note": "решающая модель: только choice/score/noul, текста не пишет",
    },
]


@dataclass
class Model:
    """One catalogue entry, flattened to what a choice actually needs."""

    id: str
    name: str
    price_in: float
    price_out: float
    context: int
    max_out: int
    intelligence: float | None
    coding: float | None
    agentic: float | None
    tools: bool
    structured: bool
    reasoning_efforts: list[str] = field(default_factory=list)
    modalities: str = "text"
    note: str = ""

    @property
    def blended(self) -> float:
        """Price per 1M tokens at a 3:1 input:output mix.

        A single number is a crude proxy, but it makes 'cheap' comparable at a
        glance. The real mix depends on the task — read the two columns when it
        matters.
        """
        return (self.price_in * 3 + self.price_out) / 4

    @property
    def value(self) -> float | None:
        """Intelligence per dollar. Higher is better; meaningless without a score."""
        if self.intelligence is None or self.blended <= 0:
            return None
        return self.intelligence / self.blended


def per_million(raw: Any) -> float:
    """OpenRouter prices are per token as strings; convert to per 1M."""
    try:
        return float(raw) * 1_000_000
    except (TypeError, ValueError):
        return 0.0


def parse(entry: dict[str, Any]) -> Model:
    pricing = entry.get("pricing") or {}
    arch = entry.get("architecture") or {}
    benches = entry.get("benchmarks") or {}
    aa = benches.get("artificial_analysis") or {}
    reasoning = entry.get("reasoning") or {}
    params = entry.get("supported_parameters") or []
    provider = entry.get("top_provider") or {}

    return Model(
        id=entry["id"],
        name=entry.get("name") or entry["id"],
        price_in=per_million(pricing.get("prompt")),
        price_out=per_million(pricing.get("completion")),
        context=int(entry.get("context_length") or 0),
        max_out=int(provider.get("max_completion_tokens") or 0),
        intelligence=_num(aa.get("intelligence_index")),
        coding=_num(aa.get("coding_index")),
        agentic=_num(aa.get("agentic_index")),
        tools="tools" in params,
        structured="structured_outputs" in params or "response_format" in params,
        reasoning_efforts=list(reasoning.get("supported_efforts") or []),
        modalities=_modalities(arch),
        note=entry.get("note", ""),
    )


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _modalities(arch: dict[str, Any]) -> str:
    inputs = arch.get("input_modalities") or []
    parts = []
    if "text" in inputs:
        parts.append("текст")
    if "image" in inputs:
        parts.append("картинки")
    if "file" in inputs or "pdf" in inputs:
        parts.append("файлы")
    if "audio" in inputs:
        parts.append("аудио")
    return "+".join(parts) or "—"


def fetch(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "talentflow-catalog/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"не удалось получить каталог: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def load_models(*, include_known_missing: bool = True) -> list[Model]:
    payload = fetch(API)
    entries = payload.get("data", [])
    models = [parse(e) for e in entries]
    if include_known_missing:
        present = {m.id for m in models}
        models.extend(parse(e) for e in KNOWN_MISSING if e["id"] not in present)
    return models


def select(
    models: list[Model],
    *,
    has: list[str],
    text_only: bool,
    exclude_free_output: bool,
) -> list[Model]:
    out = models
    for capability in has:
        if capability == "tools":
            out = [m for m in out if m.tools]
        elif capability == "structured":
            out = [m for m in out if m.structured]
        elif capability == "reasoning":
            out = [m for m in out if m.reasoning_efforts]
    if text_only:
        out = [m for m in out if "текст" in m.modalities]
    if exclude_free_output:
        out = [m for m in out if m.price_out > 0]
    return out


SORTS = {
    "price": lambda m: m.blended,
    "input": lambda m: m.price_in,
    "output": lambda m: m.price_out,
    "value": lambda m: -(m.value if m.value is not None else float("-inf")),
    "intelligence": lambda m: -(m.intelligence if m.intelligence is not None else float("-inf")),
    "context": lambda m: -m.context,
}


def table(models: list[Model]) -> str:
    head = (
        "| модель | вход $/1M | выход $/1M | контекст | ум | код | агент | "
        "инстр. | JSON | reasoning | модальности |"
    )
    rule = "|---|---:|---:|---:|---:|---:|---:|:---:|:---:|:---:|---|"

    def cell(v: float | None) -> str:
        return "—" if v is None else f"{v:.1f}"

    def tick(value: bool) -> str:
        return "✓" if value else "—"

    def level(m: Model) -> str:
        if not m.reasoning_efforts:
            return "—"
        if len(m.reasoning_efforts) == 1:
            return m.reasoning_efforts[0]
        return f"{len(m.reasoning_efforts)} ур."

    rows = [
        f"| `{m.id}`{(' — ' + m.note) if m.note else ''} | {m.price_in:.3f} | {m.price_out:.3f} | "
        f"{m.context:,} | {cell(m.intelligence)} | {cell(m.coding)} | {cell(m.agentic)} | "
        f"{tick(m.tools)} | {tick(m.structured)} | {level(m)} | {m.modalities} |"
        for m in models
    ]
    return "\n".join([head, rule, *rows])


def main() -> int:
    parser = argparse.ArgumentParser(description="Сравнение моделей OpenRouter")
    parser.add_argument("--sort", choices=sorted(SORTS), default="price")
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--filter", default="", help="подстрока в id")
    parser.add_argument(
        "--has", action="append", default=[], choices=["tools", "structured", "reasoning"]
    )
    parser.add_argument("--all-modalities", action="store_true", help="включая картинки и аудио")
    parser.add_argument(
        "--with-free-output", action="store_true", help="включая модели с бесплатным выходом"
    )
    parser.add_argument("--json", type=Path, help="сохранить полный снимок")
    args = parser.parse_args()

    models = load_models()
    if args.filter:
        models = [m for m in models if args.filter.lower() in m.id.lower()]
    models = select(
        models,
        has=args.has,
        text_only=not args.all_modalities,
        exclude_free_output=not args.with_free_output,
    )
    models.sort(key=SORTS[args.sort])

    shown = models[: args.top]
    print(f"# Модели OpenRouter ({len(models)} подходят, показаны {len(shown)})\n")
    print(f"Сортировка: **{args.sort}**. Цены за 1 млн токенов.\n")
    print(table(shown))

    scored = [m for m in models if m.value is not None]
    if scored:
        best = max(scored, key=lambda m: m.value)
        print(
            f"\nЛучшая отдача за деньги: `{best.id}` — ум {best.intelligence}, "
            f"${best.blended:.3f}/1M (индекс {best.value:.1f})"
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                [
                    {
                        "id": m.id,
                        "name": m.name,
                        "price_in": m.price_in,
                        "price_out": m.price_out,
                        "context": m.context,
                        "max_out": m.max_out,
                        "intelligence": m.intelligence,
                        "coding": m.coding,
                        "agentic": m.agentic,
                        "tools": m.tools,
                        "structured": m.structured,
                        "reasoning_efforts": m.reasoning_efforts,
                        "modalities": m.modalities,
                    }
                    for m in models
                ],
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        print(f"\nСнимок сохранён: {args.json} ({len(models)} моделей)", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
