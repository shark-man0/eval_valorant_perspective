import cv2
import numpy as np
import pytest

from scripts.map_learning.phase_portrait import phase_portraits
from scripts.map_learning.portrait_cohort import portrait_seconds
from scripts.map_learning.replay_temporal_portraits import (
    proposals,
    public_supported_runs,
    tracked_runs,
)
from scripts.map_learning.temporal_portrait_model import FEATURES, SCHEMA, pair_features, read_model
from valorant_ai_coach.temporal.map_direct_recorder import DirectPeak
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


def test_weak_public_pixels_require_strong_current_portraits_on_both_sides():
    assert list(public_supported_runs(list(range(6)), [0, 1, 0, 0, 1, 0])) == [[1, 2, 3, 4]]
    assert list(public_supported_runs(list(range(6)), [1, 0, 0, 0, 0, 1])) == []
    assert list(public_supported_runs(list(range(3)), [1, 0, 0])) == []


def test_incumbent_phase_search_keeps_threshold_and_measures_shifted_pixels():
    image = np.zeros((90, 1920, 3), np.uint8)
    center = (43, 40)
    image[34:47, 37:50] = np.random.default_rng(90).integers(10, 130, (13, 13, 3))
    cv2.circle(image, center, 8, (130, 200, 250), 1)
    image[center[1], center[0]] = (7, 55, 211)
    peak = DirectPeak((41, 40), 0.9, 15, 6, 0)

    def public(_image, _center):
        return np.array([0.82, 0.61])

    def cnn(patches):
        return np.where((patches[:, 8, 8] == [7, 55, 211]).all(axis=1), 0.88, 0.79)

    ((measured, evidence),) = phase_portraits(image, (0, 0, 90, 90), [peak], cnn, public, 0)
    assert measured == center
    assert evidence["initial_peak_roi_px"] == (41, 40)
    assert not phase_portraits(
        image, (0, 0, 90, 90), [peak], lambda patches: np.full(len(patches), 0.79), public, 0
    )


def test_gallery_proposal_order_matches_second_template_agreement(monkeypatch):
    rng = np.random.default_rng(2)
    roi = rng.integers(0, 255, (60, 80, 3), dtype=np.uint8)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    templates = tuple(gray[y : y + 11, x : x + 11].copy() for x, y in ((2, 3), (20, 10), (32, 42)))
    fields = np.stack([cv2.matchTemplate(gray, item, cv2.TM_CCOEFF_NORMED) for item in templates])
    joint = np.partition(fields, -2, axis=0)[-2]
    peaks = np.argwhere(joint == cv2.dilate(joint, np.ones((7, 7), np.uint8)))
    ranked = sorted(peaks, key=lambda p: (-joint[*p], *p))[:14]
    expected = [
        ((int(j) + 5, int(i) + 5), (16, 8, 0))
        for i, j in ranked
        if 11 <= int(j) + 5 < 69 and 11 <= int(i) + 5 < 49
    ]
    monkeypatch.setattr(
        "scripts.map_learning.replay_temporal_portraits._rim_evidence",
        lambda *_: (16, 8, 0),
    )
    assert list(proposals(roi, templates, 1)) == expected
