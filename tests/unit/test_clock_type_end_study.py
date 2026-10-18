"""Research-only synthetic clocks. No real GT, qualified events or reader claims."""

from dataclasses import replace
from fractions import Fraction

import pytest

from scripts.diagnostics.clock_type_end_study import ActiveContext, ClockTypeEndStudy, Sample


def samples():
    return [
        Sample(
            "a" * 64,
            "epoch",
            i * 20,
            Fraction(1, 1000),
            f"{i:064x}",
            "spike" if i < 16 else "unknown" if i == 16 else "decimal",
            "25.28" if i >= 17 else None,
            0.95,
            (0, int(i >= 16)),
            0.95,
            "complete" if i >= 30 else "absent",
            0.95,
            "active",
            "global",
        )
        for i in range(1, 80)
    ]


def replay(rows, *, context=True):
    ctx = ActiveContext("a" * 64, "epoch", 0, "d" * 64) if context else None
    study = ClockTypeEndStudy(20, ctx)
    decisions = [p for row in rows if (p := study.advance(row)) is not None]
    return decisions, study


def test_positive_pattern_keeps_actual_score_tick_and_cannot_release_formal_end():
    decisions, study = replay(samples())
    assert len(decisions) == 1 and study.ended
    pattern = decisions[0]
    assert pattern.boundary_tick == 320  # Score first observed, not clock's later tick340.
    assert pattern.confirmation_tick == 700
    assert pattern.formal_release is False
    assert pattern.scope == "unqualified_clock_type_contract_study"


@pytest.mark.parametrize(
    "failure",
    [
        "numeric_only",
        "spike_only",
        "decimal_only",
        "score_only",
        "clock_only",
        "partial_caption",
        "stale_caption",
        "unknown_caption",
        "buy",
        "spectator",
        "unknown_view",
        "unknown_clock",
        "source_break",
        "pts_gap",
        "repeated_raster",
        "foreign_epoch",
        "unknown_score",
        "score_rollback",
        "late_caption",
        "late_decimal",
        "decimal_changes",
        "occlusion",
        "clock_weak",
        "score_weak",
    ],
)
def test_negative_cannot_form_even_a_research_pattern(failure):
    rows = samples()
    if failure in {"numeric_only", "spike_only", "decimal_only", "unknown_clock"}:
        kind = {
            "numeric_only": "numeric",
            "spike_only": "spike",
            "decimal_only": "decimal",
            "unknown_clock": "unknown",
        }[failure]
        rows = [replace(x, clock_kind=kind) for x in rows]
    elif failure == "score_only":
        rows = [replace(x, clock_kind="numeric") for x in rows]
    elif failure == "clock_only":
        rows = [replace(x, score=(0, 0)) for x in rows]
    elif failure in {"partial_caption", "stale_caption", "unknown_caption"}:
        caption = {
            "partial_caption": "partial",
            "stale_caption": "complete",
            "unknown_caption": "unknown",
        }[failure]
        rows = [replace(x, caption=caption) for x in rows]
    elif failure == "buy":
        rows[18] = replace(rows[18], phase="buy")
    elif failure in {"spectator", "unknown_view"}:
        rows[18] = replace(rows[18], view="spectator" if failure == "spectator" else "unknown")
    elif failure == "source_break":
        rows[18] = replace(rows[18], source_break=True)
    elif failure == "pts_gap":
        rows.pop(18)
    elif failure == "repeated_raster":
        rows[18] = replace(rows[18], pixel=rows[17].pixel)
    elif failure == "foreign_epoch":
        rows[18] = replace(rows[18], epoch="new_epoch")
    elif failure == "unknown_score":
        rows[18] = replace(rows[18], score=None)
    elif failure == "score_rollback":
        rows[18] = replace(rows[18], score=(0, 0))
    elif failure == "late_caption":
        rows = [replace(x, caption="absent" if x.tick <= 1320 else "complete") for x in rows]
    elif failure == "late_decimal":
        rows[16] = replace(rows[16], clock_kind="unknown", clock_literal=None)
    elif failure == "decimal_changes":
        rows[18] = replace(rows[18], clock_literal="25.29")
    elif failure == "occlusion":
        rows[18] = replace(rows[18], occluded=True)
    elif failure == "clock_weak":
        rows = [replace(x, clock_confidence=0.89) for x in rows]
    elif failure == "score_weak":
        rows[15] = replace(rows[15], score_confidence=0.89)
    assert replay(rows)[0] == []


def test_no_active_start_fragment_and_duplicate_end_stay_closed():
    rows = samples()
    assert replay(rows, context=False)[0] == []
    decisions, study = replay(rows)
    assert len(decisions) == 1
    # Even a second synthetic type/score sequence cannot rearm without a new context.
    for row in rows:
        assert study.advance(replace(row, tick=row.tick + 1600, pixel="f" * 64)) is None


def test_unknown_score_cannot_be_filled_from_a_previous_stable_run():
    rows = samples()
    rows[14] = replace(rows[14], score=None)
    assert replay(rows)[0] == []


def test_saved_sequence_replay_is_deterministic_and_does_not_mutate_samples():
    from copy import deepcopy

    from scripts.diagnostics.clock_type_end_study import replay_samples

    rows = samples()
    original = deepcopy(rows)
    ctx = ActiveContext("a" * 64, "epoch", 0, "d" * 64)
    assert replay_samples(rows, 20, ctx) == replay_samples(rows, 20, ctx)
    assert rows == original
    assert replay_samples(rows, 20)["last_blocker"] == "no_active_context"


@pytest.mark.parametrize(
    "change",
    [
        {"tick": -1},
        {"tick": True},
        {"pixel": "invalid"},
    ],
)
def test_malformed_source_identity_abstains(change):
    rows = samples()
    rows[18] = replace(rows[18], **change)
    assert replay(rows)[0] == []
