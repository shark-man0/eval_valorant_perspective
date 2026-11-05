"""Streaming/adaptive acquisition boundaries, without private video or labels."""

from fractions import Fraction
from io import BytesIO

import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.match import png_frames, refinement_windows
from valorant_ai_coach.temporal.match_observer import _reject_identity_configuration


def png(value):
    ok, encoded = cv2.imencode(".png", np.full((32, 48, 3), value, dtype=np.uint8))
    assert ok
    return encoded.tobytes()


class Fragmented(BytesIO):
    def read(self, size=-1):
        return super().read(min(size, 3))


def test_png_pipe_preserves_two_distinct_encoded_frames_across_short_reads():
    frames = [png(20), png(180)]
    assert list(png_frames(Fragmented(b"".join(frames)))) == frames


@pytest.mark.parametrize("mutate", [lambda v: v[:-1], lambda v: v[:10], lambda v: b"invalid!" + v])
def test_truncated_or_invalid_png_is_not_a_successful_observation(mutate):
    with pytest.raises(ValueError):
        list(png_frames(BytesIO(mutate(png(20)))))


def test_png_declared_chunk_size_is_bounded_before_reading_the_payload():
    value = b"\x89PNG\r\n\x1a\n" + (2**30).to_bytes(4, "big") + b"IDAT"
    with pytest.raises(ValueError, match="memory budget"):
        list(png_frames(BytesIO(value)))


def point(second, *, signals=(), score=None, clock=None, marker=False):
    return {
        "sample": {"native_pts_tick": second * 10, "native_time_base": "1/10"},
        "measurement": {
            "signals": list(signals),
            "context": {"score": score, "timer_seconds": clock},
            "map_candidates": [{"candidate": True}] if marker else [],
        },
    }


def test_regular_countdown_does_not_request_dense_video():
    records = [point(i, signals=["active"], score=[1, 2], clock=100 - i) for i in range(8)]
    assert refinement_windows(records, max_windows=40) == ([], 0)


@pytest.mark.parametrize(
    "change", [dict(signals=["spectator"]), dict(score=[1, 0]), dict(clock=100), dict(marker=True)]
)
def test_current_display_changes_request_native_context_without_game_time_hints(change):
    windows, deferred = refinement_windows([point(0), point(1, **change)], max_windows=40)
    if "clock" in change:
        assert windows == []  # an unknown clock is not a measured timer jump
    else:
        assert windows == [(Fraction(0), Fraction(2))]
    assert deferred == 0


def test_dense_budget_defers_windows_explicitly():
    rows = [
        point(0),
        point(1, signals=["buy"]),
        point(10, signals=["buy"]),
        point(11, signals=["active"]),
    ]
    windows, deferred = refinement_windows(rows, max_windows=0)
    assert windows == [] and deferred == 2


@pytest.mark.parametrize("field", ["source_id", "recorder_agent_id", "initial_state"])
def test_source_condition_or_roster_is_rejected_inside_nested_reader_settings(field):
    with pytest.raises(ValueError):
        _reject_identity_configuration({"reader": {"conditions": [{field: "case"}]}})


def test_training_asset_provenance_can_be_retained_without_becoming_a_condition():
    _reject_identity_configuration({"phase_reference_provenance": {"source_sha256": "a" * 64}})


def test_persistent_display_flicker_cannot_exceed_the_dense_duration_budget():
    rows = [point(i, signals=["buy"] if i % 2 else ["active"]) for i in range(500)]
    windows, deferred = refinement_windows(rows, max_windows=40)
    assert sum(b - a for a, b in windows) == 240
    assert deferred == 1


def test_refinement_respects_a_nonzero_native_origin():
    windows, _ = refinement_windows(
        [point(6), point(7, signals=["active"])], max_windows=40, origin=Fraction(11, 2)
    )
    assert windows == [(Fraction(11, 2), Fraction(8))]


def test_balanced_selection_retains_a_late_explicit_edge_after_early_flicker():
    rows = [point(i, signals=["owner_hud"] if i % 2 else []) for i in range(100)]
    rows += [point(i, signals=["buy"] if i < 201 else ["active"]) for i in range(100, 300)]
    legacy, _ = refinement_windows(rows, max_windows=4, max_total_seconds=Fraction(24))
    balanced, deferred = refinement_windows(
        rows, max_windows=4, max_total_seconds=Fraction(24), selection_policy="balanced"
    )
    assert not any(a <= 201 <= b for a, b in legacy)
    assert any(a <= 201 <= b for a, b in balanced)
    assert sum(b - a for a, b in balanced) <= 24
    assert deferred > 0  # the large flickering prefix was not fully refined


def test_balanced_strata_cover_changes_across_the_recording():
    rows = [point(i, signals=["buy"] if (i // 10) % 2 else ["active"]) for i in range(401)]
    windows, _ = refinement_windows(rows, max_windows=4, selection_policy="balanced")
    assert len(windows) == 4
    for lower, upper in [(0, 100), (100, 200), (200, 300), (300, 401)]:
        assert any(lower <= (a + b) / 2 < upper for a, b in windows)


def test_balanced_prefers_measured_round_change_to_missing_value_chatter():
    rows = [point(i, signals=["buy"] if i < 11 else ["active"],
                  score=[0, 0] if i % 2 else None) for i in range(31)]
    windows, _ = refinement_windows(rows, max_windows=1, selection_policy="balanced")
    assert any(a <= 11 <= b for a, b in windows)
    assert sum(b - a for a, b in windows) <= 6


def test_balanced_tiny_budget_remains_bounded_and_reports_partial_regions():
    rows = [point(i, signals=["buy"] if i % 2 else ["active"]) for i in range(30)]
    windows, deferred = refinement_windows(
        rows, max_windows=40, max_total_seconds=Fraction(1, 2), selection_policy="balanced"
    )
    assert sum(b - a for a, b in windows) <= Fraction(1, 2)
    assert deferred == 1


def test_balanced_selection_is_invariant_to_native_origin_and_identity_metadata():
    rows = [point(i, signals=["buy"] if (i // 4) % 2 else ["active"]) for i in range(40)]
    expected, count = refinement_windows(rows, max_windows=3, selection_policy="balanced")
    shifted = []
    for row in rows:
        sample = {**row["sample"], "native_pts_tick": row["sample"]["native_pts_tick"] + 1230,
                  "source_id": "different", "recorder_agent_id": "unused"}
        shifted.append({**row, "sample": sample})
    actual, shifted_count = refinement_windows(
        shifted, max_windows=3, origin=Fraction(123), selection_policy="balanced"
    )
    assert actual == [(a + 123, b + 123) for a, b in expected]
    assert count == shifted_count


@pytest.mark.parametrize("rows", [[], [point(0)], [point(0), point(1)]])
def test_balanced_empty_or_unchanging_input_requests_no_dense_frames(rows):
    assert refinement_windows(rows, max_windows=40, selection_policy="balanced") == ([], 0)


@pytest.mark.parametrize("policy", ["unknown", "", None])
def test_unknown_refinement_policy_is_rejected(policy):
    with pytest.raises(ValueError, match="selection policy"):
        refinement_windows([point(0), point(1)], max_windows=40, selection_policy=policy)
