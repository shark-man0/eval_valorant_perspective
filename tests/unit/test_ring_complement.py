"""Corroboration must preserve exact old points and abstain at contradictory evidence."""

from copy import deepcopy

import numpy as np
import pytest

from scripts.map_learning.ring_complement import complement
from valorant_ai_coach.temporal import map_view_episodes
from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.map_recorder_path import (
    join_recorder_seconds,
    measured_native_edges,
)


def inputs(monkeypatch):
    monkeypatch.setattr(map_view_episodes, "measure_recorder_view", lambda f, _: ("view", False))
    frames, rows = {}, {}
    for n in range(5):
        sample = freeze_native_sample(
            {
                "source_id": "s",
                "source_sha256": "a" * 64,
                "acquisition_id": "native",
                "native_epoch": "native",
                "native_pts_tick": n * 3072,
                "native_time_base": "1/15360",
                "native_pixel_sha256": f"{n + 1:064x}",
                "acquired_frame_sha256": f"{n + 10:064x}",
                "frame_size_px": [1920, 1080],
            }
        )
        key = sample["sample_sha256"]
        frames[key] = {
            "sample": sample,
            "camera": {"value": "SELF"},
            "life": {"value": "ALIVE"},
            "round": {"value": "ACTIVE"},
            "observation_ids": [],
            "continuity": {"carry_allowed": True},
            "tracking_epoch": "one",
        }
        rows[key] = {
            "ring": {"status": "UNIQUE", "center_roi_px": [100 + n, 100]},
            "center_frame_px": [120 + n, 148],
            "roi_pixel_sha256": "d" * 64,
            "fit": {
                "roi_pixel_sha256": "d" * 64,
                "map_name_candidates": [
                    {
                        "map_id": "map",
                        "fit_residual_p95_reference_px": 2,
                        "reference_to_roi_homography_candidate": np.eye(3).tolist(),
                    }
                ],
            },
        }
    timeline = {
        "native_frames": frames,
        "observations": {},
        "seconds": [{"timestamp": 0, "sample_refs": list(frames)}],
    }
    base = {
        "schema": "development_recorder_map_path_v1",
        "qualified": False,
        "formal_outputs": 0,
        "interpolated_samples": 0,
        "segments": [],
    }
    base["second_rows"] = join_recorder_seconds(base, timeline)
    return timeline, base, rows


def apply(timeline, base, rows):
    return complement(
        timeline,
        base,
        rows,
        map_id="map",
        reference_sha256="e" * 64,
        atlas_distances=np.zeros((200, 200), np.float32),
        operable=set(timeline["native_frames"]),
        receipt_sha256="f" * 64,
    )


def test_measured_runs_add_real_points_and_preserve_baseline_edges(monkeypatch):
    timeline, base, rows = inputs(monkeypatch)
    seed = apply(timeline, base, rows)
    base["segments"] = [deepcopy(seed["segments"][0][:2])]
    original = deepcopy(base)
    result = apply(timeline, base, rows)
    assert result["segments"][0] == original["segments"][0]
    assert base == original
    assert measured_native_edges(base) <= measured_native_edges(result)
    added = result["ring_complement"]["added_evidence"]
    assert len(added) == 3
    assert set(added) <= timeline["native_frames"].keys()
    assert result["interpolated_samples"] == result["formal_outputs"] == 0


@pytest.mark.parametrize("failure", ["ambiguous", "registration", "missing", "dead"])
def test_unmeasured_or_ambiguous_middle_cannot_bridge_two_short_runs(monkeypatch, failure):
    timeline, base, rows = inputs(monkeypatch)
    key = list(rows)[2]
    if failure == "ambiguous":
        rows[key]["ring"]["status"] = "AMBIGUOUS"
    elif failure == "registration":
        rows[key]["fit"] = None
    elif failure == "missing":
        del rows[key]
    else:
        timeline["native_frames"][key]["life"]["value"] = "DEAD"
    assert apply(timeline, base, rows)["segments"] == []


def test_conflict_with_an_existing_point_abstains_for_the_entire_run(monkeypatch):
    timeline, base, rows = inputs(monkeypatch)
    point = deepcopy(apply(timeline, base, rows)["segments"][0][2])
    point["map_reference_px"] = [160, 100]
    base["segments"] = [[point]]
    result = apply(timeline, base, rows)
    assert result["segments"] == [[point]]
    assert result["ring_complement"]["added_evidence"] == {}


def test_registration_and_detector_must_measure_identical_pixels(monkeypatch):
    timeline, base, rows = inputs(monkeypatch)
    rows[next(iter(rows))]["fit"]["roi_pixel_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="different pixels"):
        apply(timeline, base, rows)


def test_registration_flip_cannot_create_a_long_world_coordinate_jump(monkeypatch):
    timeline, base, rows = inputs(monkeypatch)
    for key in list(rows)[2:]:
        # A visually stable icon must not hide a jump in atlas registration.
        rows[key]["fit"]["map_name_candidates"][0]["reference_to_roi_homography_candidate"] = [
            [1, 0, -70],
            [0, 1, 0],
            [0, 0, 1],
        ]
    result = apply(timeline, base, rows)
    assert len(result["segments"]) == 1
    assert len(result["segments"][0]) == 3
    assert len(measured_native_edges(result)) == 2
