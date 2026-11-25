import numpy as np
import pytest

from scripts.map_learning.portrait_cohort import portrait_seconds
from scripts.map_learning.replay_temporal_portraits import tracked_runs
from scripts.map_learning.temporal_portrait_model import FEATURES, SCHEMA, pair_features, read_model
from valorant_ai_coach.temporal.replay import write_private


def _point(tick, xy, map_id="map"):
    return {
        "sample": {"native_pts_tick": tick, "native_time_base": "1/5"},
        "map_id": map_id,
        "reference_sha256": "r",
        "map_reference_px": list(xy),
    }


def test_tracks_keep_only_unique_consecutive_measured_positions():
    points = [_point(i, (8 * i, 0)) for i in range(6)]
    assert list(tracked_runs([[p] for p in points[:3]])) == [points[:3]]
    assert list(tracked_runs([[points[0]], [], [points[2]], [points[3]]])) == []
    rival = [_point(i, (10 * i, 300)) for i in range(3)]
    assert list(tracked_runs([[a, b] for a, b in zip(points[:3], rival, strict=True)])) == []
    unrelated = _point(2, (16, 0), "different-map")
    assert not list(tracked_runs([[points[0]], [points[1]], [unrelated]]))


def test_gap_cohort_requires_every_current_measurement_to_be_rejected_by_both():
    seconds = [
        {"timestamp": i, "sample_refs": [a, b]}
        for i, (a, b) in enumerate((("a", "b"), ("c", "d"), ("e", "f"), ("g", "h")))
    ]
    report = {
        "second_rows": [
            {"timestamp": i, "recorder_map_observations": [1] if i == 3 else []} for i in range(4)
        ]
    }
    reference = {
        "comparison_evidence": {
            "operable_sample_refs": list("abcdefg"),
            "unresolved_portrait_sample_refs": list("abcdefgh"),
        }
    }
    adaptive = {"comparison_evidence": {"unresolved_portrait_sample_refs": list("abcegh")}}
    assert portrait_seconds({"seconds": seconds}, report, reference, adaptive) == {0: ("a", "b")}


def test_temporal_metric_refuses_its_own_physical_matches(tmp_path):
    path = tmp_path / "private.json"
    write_private(
        path,
        {
            "schema": SCHEMA,
            "formal_outputs": 0,
            "feature_order": list(FEATURES),
            "training_physical_matches": ["training"],
            "calibration_physical_matches": ["tuning"],
            "weights": [1, 0, 0, 0, 0, 0],
            "bias": 0.0,
            "threshold": 0.9,
            "training_receipt_sha256": "a" * 64,
            "calibration_receipt_sha256": "b" * 64,
            "hard_index_sha256": "c" * 64,
        },
    )
    for match in ("training", "tuning"):
        with pytest.raises(ValueError, match="disjoint"):
            read_model(path, match)
    assert read_model(path, "unseen")["threshold"] == 0.9
    descriptor = np.arange(243, dtype=float)
    descriptor /= np.linalg.norm(descriptor)
    assert pair_features(descriptor, descriptor).tolist() == pytest.approx([1] * 6)
