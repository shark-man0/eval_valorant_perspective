from fractions import Fraction

from tests.unit.test_shared_match_sampling import point
from valorant_ai_coach.temporal.match import refinement_windows


def report_point(t, *, unresolved=True):
    row = point(t)
    row["measurement"]["supplier_observations"] = [
        {
            "raw": {"owned_verb_phrase": "owned_display_relation"},
            "context": {} if unresolved else {"elimination_display_signature": "a" * 64},
        }
    ]
    return row


def test_unresolved_report_onset_gets_bounded_followup_even_with_round_flicker():
    rows = [point(0), report_point(1), report_point(2)]
    windows, _ = refinement_windows(rows, max_windows=2, selection_policy="evidence")
    assert any(a <= 1 and b >= 4 for a, b in windows)
    assert sum(b - a for a, b in windows) <= 240


def test_resolved_report_and_zero_budget_do_not_force_inspection():
    rows = [point(0), report_point(1, unresolved=False)]
    assert refinement_windows(rows, max_windows=2, selection_policy="evidence")[0] == []
    assert (
        refinement_windows([point(0), report_point(1)], max_windows=0, selection_policy="evidence")[
            0
        ]
        == []
    )


def test_report_priority_is_time_translation_invariant():
    rows = [point(0), report_point(1)]
    chosen, _ = refinement_windows(rows, max_windows=2, selection_policy="evidence")
    shifted = [point(100), report_point(101)]
    actual, _ = refinement_windows(
        shifted, max_windows=2, selection_policy="evidence", origin=Fraction(100)
    )
    assert actual == [(a + 100, b + 100) for a, b in chosen]
