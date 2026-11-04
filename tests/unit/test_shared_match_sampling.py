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
