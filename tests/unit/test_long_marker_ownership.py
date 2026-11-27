import math
from fractions import Fraction

import numpy as np
import pytest

from scripts.map_learning.acquire_marker_context import _ranges, _selection_expression
from scripts.map_learning.long_marker_ownership import (
    FEATURES,
    MATCH_SCHEMA,
    extension,
    pair_features,
    read_match_profile,
)
from scripts.map_learning.marker_tracks import Marker, Track
from valorant_ai_coach.temporal.replay import write_private


def test_round_anchor_extends_past_old_window_and_stops_before_a_competing_link():
    frames = [
        Marker(str(i), i, Fraction(i, 5), (i, 9), "WARM", 8.0, 20, 8, np.ones(49) / 7)
        for i in range(12)
    ]
    track = Track(frames, {(str(i), str(i + 1)): 0.5 for i in range(11)})
    evidence = {(m.sample_ref, m.center): (i == 0, 0.8, 0.2, False) for i, m in enumerate(frames)}
    unique = {m.sample_ref: 1 for m in frames}
    actual = extension(
        track,
        [],
        evidence,
        unique,
        "observed_round_start",
        Fraction(0),
        {("8", (8, 9))},
        None,
    )
    assert "7" in actual and actual["7"]["elapsed_seconds"] > 0.8
    assert actual["7"]["round_start_seed"]
    assert "8" not in actual and "9" not in actual
    assert not extension(
        track, [], evidence, unique, "current_view_gap_or_change", Fraction(0), set(), None
    )


def test_match_profile_rejects_evaluation_match_and_shared_calibration(tmp_path):
    path = tmp_path / "match.json"
    write_private(
        path,
        {
            "schema": MATCH_SCHEMA,
            "formal_outputs": 0,
            "feature_order": list(FEATURES),
            "cutoff": 0.5,
            "weights": [1.0] * len(FEATURES),
            "source_receipts": ["a" * 64],
            "training_matches": ["train"],
            "calibration_matches": ["calibration"],
        },
    )
    assert read_match_profile(path, "unseen")["cutoff"] == 0.5
    with pytest.raises(ValueError, match="disjoint"):
        read_match_profile(path, "train")
    with pytest.raises(ValueError, match="disjoint"):
        read_match_profile(path, "calibration")


def test_multipoint_appearance_similarity_is_symmetric():
    a = np.zeros(49)
    a[20:29] = 1
    b = np.roll(a, 6)
    assert np.allclose(pair_features(a, b), pair_features(b, a))
    assert pair_features(a, a)[0] == pytest.approx(1)


def test_context_filter_respects_unrequested_sample_between_ranges():
    ranges = _ranges({2, 3, 7}, [2, 3, 5, 7, 8])
    assert ranges == [(2, 3), (7, 7)]
    assert _selection_expression(ranges) == "if(lt(pts,7),between(pts,2,3),between(pts,7,7))"


def test_current_outline_rejects_a_flat_patch_after_track_drift():
    import cv2

    from scripts.map_learning.marker_quality import enclosing_outline

    image = np.full((160, 1920, 3), 80, dtype=np.uint8)
    assert enclosing_outline(image, (70, 70)) is None
    cv2.circle(image, (70, 70), 8, (160, 220, 240), 2)
    cv2.rectangle(image, (67, 65), (71, 74), (20, 30, 100), -1)
    outline = enclosing_outline(image, (70, 70))
    assert outline is not None
    assert math.dist(outline["center_frame_px"], (70, 70)) <= 3
