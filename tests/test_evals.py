"""Tests for the evaluation metrics.

The statistics are the part of Day 5 that can be verified without a model, so
they are tested against hand-computed values rather than against themselves.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from talentflow.evals import (
    Interval,
    confusion_at,
    evaluate,
    pick_threshold,
    summarise,
    sweep,
    wilson_interval,
)

FIXTURE = Path(__file__).parent / "fixtures" / "labeled_vacancies.json"


# --- the interval itself ---------------------------------------------------


def test_wilson_matches_a_hand_computed_value() -> None:
    """24 of 30 gives p=0.8; Wilson puts the 95% bounds at 0.627 and 0.905."""
    interval = wilson_interval(24, 30)

    assert interval.value == pytest.approx(0.8, abs=1e-9)
    assert interval.low == pytest.approx(0.627, abs=0.005)
    assert interval.high == pytest.approx(0.905, abs=0.005)


def test_wilson_interval_is_narrow_at_thirty_examples() -> None:
    """The width is the reason single F1 numbers are reported with bounds.

    ±14 percentage points on 30 examples means two configurations differing by
    5 points are indistinguishable — the core caveat of this whole evaluation.
    """
    interval = wilson_interval(24, 30)

    assert 0.25 < interval.width < 0.31
    assert interval.high - interval.value == pytest.approx(0.105, abs=0.01)


def test_wilson_narrows_as_the_sample_grows() -> None:
    small = wilson_interval(8, 10)
    large = wilson_interval(800, 1000)

    assert large.width < small.width


def test_wilson_stays_inside_zero_and_one() -> None:
    """The normal approximation can exceed 1; Wilson must not."""
    for successes, total in [(30, 30), (29, 30), (0, 30), (1, 30), (1, 1)]:
        interval = wilson_interval(successes, total)
        assert 0.0 <= interval.low <= interval.value <= interval.high <= 1.0


def test_wilson_handles_a_perfect_score_without_claiming_certainty() -> None:
    """30 of 30 is not proof of 100%: the lower bound must stay below 1."""
    interval = wilson_interval(30, 30)

    assert interval.value == 1.0
    assert interval.low < 0.9


def test_wilson_handles_an_empty_sample() -> None:
    """Nothing measured reports nothing, rather than raising."""
    assert wilson_interval(0, 0) == Interval(0.0, 0.0, 0.0)


def test_interval_str_shows_bounds() -> None:
    assert str(Interval(0.8, 0.627, 0.905)) == "0.800 [0.627; 0.905]"


# --- confusion matrix ------------------------------------------------------


def test_confusion_counts_every_outcome() -> None:
    scores = [0.9, 0.8, 0.7, 0.2]
    labels = [True, False, True, False]

    c = confusion_at(scores, labels, threshold=0.75)

    assert (c.true_positive, c.false_positive, c.false_negative, c.true_negative) == (1, 1, 1, 1)
    assert c.total == 4


def test_threshold_is_inclusive() -> None:
    """A score exactly at the threshold counts as predicted relevant."""
    c = confusion_at([0.6], [True], threshold=0.6)

    assert c.true_positive == 1
    assert c.false_negative == 0


def test_confusion_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="differ in length"):
        confusion_at([0.5], [True, False], threshold=0.5)


def test_confusion_on_an_empty_sample() -> None:
    c = confusion_at([], [], threshold=0.5)

    assert c.total == 0


# --- metrics ---------------------------------------------------------------


def test_evaluate_reports_precision_recall_and_f1() -> None:
    # 2 relevant, 2 not; at 0.5 the model catches both relevant plus one
    # irrelevant (0.6 scored above the threshold), so precision is not 1.
    scores = [0.9, 0.7, 0.6, 0.2]
    labels = [True, True, False, False]

    m = evaluate(scores, labels, 0.5)

    assert m.threshold == 0.5
    assert m.precision.value == pytest.approx(2 / 3)
    assert m.recall.value == pytest.approx(1.0)
    assert m.f1.value == pytest.approx(0.8)
    assert m.support == 4


def test_evaluate_with_no_positives_predicted() -> None:
    """Precision over an empty prediction set is zero, not undefined."""
    m = evaluate([0.1, 0.2], [True, False], 0.9)

    assert m.precision.value == 0.0
    assert m.confusion.predicted_positive == 0


def test_accuracy_note_explains_why_accuracy_is_absent() -> None:
    m = evaluate([0.9, 0.1, 0.1, 0.1], [True, False, False, False], 0.5)

    assert "1/4 релевантных" in m.accuracy_note


# --- sweep and threshold choice --------------------------------------------


def test_sweep_covers_every_threshold() -> None:
    results = sweep([0.2, 0.5, 0.8], [True, False, True], thresholds=[0.3, 0.6, 0.9])

    assert [m.threshold for m in results] == [0.3, 0.6, 0.9]


def test_raising_the_threshold_trades_recall_for_precision() -> None:
    """The curve is the point: one threshold is a decision, not a measurement."""
    scores = [0.9, 0.65, 0.55, 0.2]
    labels = [True, False, True, False]

    low, high = evaluate(scores, labels, 0.5), evaluate(scores, labels, 0.7)

    assert high.precision.value >= low.precision.value
    assert high.recall.value <= low.recall.value


def test_pick_threshold_respects_the_precision_floor() -> None:
    scores = [0.9, 0.85, 0.8, 0.75, 0.2]
    labels = [True, True, False, False, False]
    results = sweep(scores, labels, thresholds=[0.3, 0.7, 0.9])

    chosen = pick_threshold(results, min_precision=0.99)

    assert chosen is not None
    assert chosen.precision.value == 1.0
    assert chosen.threshold == 0.9


def test_pick_threshold_returns_none_when_nothing_qualifies() -> None:
    """No threshold clearing the floor is a result, not a failure."""
    results = sweep([0.1, 0.2], [True, False], thresholds=[0.5])

    assert pick_threshold(results, min_precision=0.9) is None


def test_summarise_renders_a_table() -> None:
    table = summarise(sweep([0.9, 0.1], [True, False], thresholds=[0.5]))

    assert "| порог |" in table
    assert "| 0.5 |" in table


# --- fixture ---------------------------------------------------------------


def test_labelled_fixture_loads() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert len(payload["vacancies"]) == 15
    assert payload["_meta"]["requires_human_confirmation"] is True


def test_fixture_labels_are_booleans_and_ids_unique() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ids = [v["id"] for v in payload["vacancies"]]

    assert len(ids) == len(set(ids)), "duplicate ids would double-count a vacancy"
    assert all(isinstance(v["relevant"], bool) for v in payload["vacancies"])


def test_fixture_has_both_classes() -> None:
    """A fixture that is all one label makes precision and recall meaningless."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    relevant = [v for v in payload["vacancies"] if v["relevant"]]

    assert 0 < len(relevant) < len(payload["vacancies"])


def test_fixture_records_its_own_bias() -> None:
    """The provenance of a label matters as much as the label."""
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    meta = payload["_meta"]

    assert "bias_warning" in meta
    assert "ПРЕДВАРИТЕЛЬНО" in meta["labeled_by"]
    assert meta["count"] < meta["planned_count"], "the shortfall must be stated, not hidden"
