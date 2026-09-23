"""Metrics for the scoring evaluation.

The numbers here are small — fifteen to thirty labelled vacancies — and at that
size a single F1 figure is misleading. On 30 examples the 95% interval around a
precision of 0.80 is roughly ±14 percentage points, so two configurations
differing by 5 points are indistinguishable. Every metric therefore comes with an
interval, and the interval is what decisions should be made on.

Wilson rather than the normal approximation: at the small samples and proportions
near 1 that this evaluation produces, the normal interval is too narrow and can
extend past 1.0, which reads as more certainty than the data supports.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

#: 95% confidence.
Z_95 = 1.96


@dataclass(frozen=True)
class Interval:
    """A point estimate with its confidence bounds."""

    value: float
    low: float
    high: float

    @property
    def width(self) -> float:
        return self.high - self.low

    def __str__(self) -> str:
        return f"{self.value:.3f} [{self.low:.3f}; {self.high:.3f}]"


def wilson_interval(successes: int, total: int, *, z: float = Z_95) -> Interval:
    """Wilson score interval for a proportion.

    Returns a zero-width interval at 0 for an empty sample rather than raising:
    an evaluation with nothing to measure should report that, not crash.
    """
    if total <= 0:
        return Interval(0.0, 0.0, 0.0)

    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return Interval(p, max(0.0, centre - margin), min(1.0, centre + margin))


@dataclass(frozen=True)
class Confusion:
    """Outcome counts for one threshold."""

    true_positive: int = 0
    false_positive: int = 0
    true_negative: int = 0
    false_negative: int = 0

    @property
    def total(self) -> int:
        return self.true_positive + self.false_positive + self.true_negative + self.false_negative

    @property
    def predicted_positive(self) -> int:
        return self.true_positive + self.false_positive

    @property
    def actual_positive(self) -> int:
        return self.true_positive + self.false_negative


def confusion_at(scores: list[float], labels: list[bool], threshold: float) -> Confusion:
    """Count outcomes for a decision rule: ``score >= threshold`` means relevant."""
    if len(scores) != len(labels):
        raise ValueError(f"scores and labels differ in length: {len(scores)} vs {len(labels)}")

    tp = fp = tn = fn = 0
    for score, relevant in zip(scores, labels, strict=True):
        predicted = score >= threshold
        if predicted and relevant:
            tp += 1
        elif predicted and not relevant:
            fp += 1
        elif not predicted and relevant:
            fn += 1
        else:
            tn += 1
    return Confusion(tp, fp, tn, fn)


@dataclass(frozen=True)
class Metrics:
    """Every number reported for one threshold."""

    threshold: float
    confusion: Confusion
    precision: Interval
    recall: Interval
    f1: Interval

    @property
    def support(self) -> int:
        """How many labelled examples the metrics rest on."""
        return self.confusion.total

    @property
    def accuracy_note(self) -> str:
        """Why accuracy is not reported.

        With a low base rate — say 15% of vacancies are relevant — a model that
        always answers 'no' scores 85% accuracy and finds nothing. Accuracy hides
        exactly the failure this evaluation exists to catch.
        """
        positives = self.confusion.actual_positive
        if self.support == 0:
            return "выборка пуста"
        return f"{positives}/{self.support} релевантных — accuracy здесь обманывает"


def evaluate(scores: list[float], labels: list[bool], threshold: float) -> Metrics:
    """Compute precision, recall and F1 with intervals at one threshold."""
    c = confusion_at(scores, labels, threshold)

    precision = wilson_interval(c.true_positive, c.predicted_positive)
    recall = wilson_interval(c.true_positive, c.actual_positive)

    # F1 has no simple exact interval: it is a ratio of two estimated
    # proportions. Bounds are taken from the precision and recall bounds, which
    # is conservative — the true interval is narrower.
    if precision.value + recall.value > 0:
        f1_point = 2 * precision.value * recall.value / (precision.value + recall.value)
        f1_low = (
            2 * precision.low * recall.low / (precision.low + recall.low)
            if (precision.low + recall.low)
            else 0.0
        )
        f1_high = (
            2 * precision.high * recall.high / (precision.high + recall.high)
            if (precision.high + recall.high)
            else 0.0
        )
    else:
        f1_point = f1_low = f1_high = 0.0

    return Metrics(
        threshold=threshold,
        confusion=c,
        precision=precision,
        recall=recall,
        f1=Interval(f1_point, f1_low, f1_high),
    )


def sweep(
    scores: list[float], labels: list[bool], thresholds: list[float] | None = None
) -> list[Metrics]:
    """Evaluate at several thresholds.

    One threshold is a decision, not a measurement. The curve shows what is being
    traded: raising the threshold buys precision with recall.
    """
    if thresholds is None:
        thresholds = [round(0.1 * n, 1) for n in range(1, 10)]
    return [evaluate(scores, labels, t) for t in thresholds]


def pick_threshold(results: list[Metrics], *, min_precision: float = 0.8) -> Metrics | None:
    """Choose the threshold with the best recall that still clears a precision floor.

    At this stage missing a good lead costs less than spending a person's time on
    a bad one, so precision is the constraint and recall is what we maximise
    under it. Returns ``None`` when no threshold clears the floor — which is a
    result, not a failure.
    """
    eligible = [m for m in results if m.precision.value >= min_precision]
    if not eligible:
        return None
    return max(eligible, key=lambda m: m.recall.value)


def summarise(results: list[Metrics]) -> str:
    """A readable table of a sweep."""
    lines = [
        "| порог | precision | recall | F1 | TP | FP | FN | TN |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for m in results:
        c = m.confusion
        lines.append(
            f"| {m.threshold:.1f} | {m.precision} | {m.recall} | {m.f1} | "
            f"{c.true_positive} | {c.false_positive} | {c.false_negative} | {c.true_negative} |"
        )
    return "\n".join(lines)
