import hashlib

import cv2
import numpy as np

from scripts.map_learning.export_sites import plant_footprints
from scripts.map_learning.recording_portraits import RecordingPortraitBank
from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.map_path_quality import measure_path_quality
from valorant_ai_coach.temporal.map_recorder_path import build_recorder_paths, join_recorder_seconds


def _sample(tick, *, source="a"):
    return freeze_native_sample({
        "source_id": source, "source_sha256": source*64, "acquisition_id": "capture",
        "native_epoch": "capture", "native_pts_tick": tick, "native_time_base": "1/5",
        "acquired_frame_sha256": "b"*64,
        "native_pixel_sha256": hashlib.sha256(str(tick).encode("ascii")).hexdigest(),
        "frame_size_px": [1920, 1080],
    })


def test_map_path_quality_excludes_unavailable_seconds_and_discontinuous_runs():
    samples = [_sample(i) for i in (0, 1, 2, 10, 15, 25)]
    positions = [
        {"sample": s, "support_count": n+1, "kind": "selected", "map_id": "map",
         "reference_sha256": "a"*64} for n, s in enumerate(samples[:3])
    ]
    path = build_recorder_paths(positions)
    ids = [s["sample_sha256"] for s in samples]
    seconds = [{"timestamp": 0, "sample_refs": ids[:3]},
               {"timestamp": 2, "sample_refs": ids[3:4]},
               {"timestamp": 3, "sample_refs": ids[4:5]},
               {"timestamp": 5, "sample_refs": ids[5:]}]
    report = measure_path_quality(
        path, seconds, join_recorder_seconds(path, {"seconds": seconds}), set(ids)-{ids[4]},
    )
    assert report["native_edges"] == 2
    assert report["longest_observed_chain_seconds"] == .4
    assert report["missing_operable_seconds"] == 2
    assert report["longest_missing_operable_run_seconds"] == 1


def test_recording_bank_requires_two_earlier_distinct_crops_and_same_source():
    bank = RecordingPortraitBank()
    roi = (0, 0, 200, 200)
    rgba = np.zeros((200, 1920, 3), np.uint8)
    cv2.circle(rgba, (45, 45), 9, (100, 199, 250), 2)
    rng = np.random.default_rng(42)
    patch = rng.integers(35, 210, (9, 9, 1), dtype=np.uint8)
    rgba[41:50, 41:50] = patch
    first, second, current = (_sample(i) for i in (0, 20, 40))
    bank.visit(first, roi)
    bank.remember(rgba, first, (45, 45))
    bank.visit(second, roi)
    bank.remember(rgba, second, (45, 45))
    assert len(bank.entries) == 1
    rgba[44, 44] = (89, 89, 89)
    bank.remember(rgba, second, (45, 45))
    bank.visit(current, roi)
    hit, = bank.peaks(rgba[:, :200], "agent", scale=1)
    assert hit.center == (45, 45)
    assert set(hit.anchor_refs) == {first["sample_sha256"], second["sample_sha256"]}
    bank.visit(_sample(45, source="f"), roi)
    assert bank.peaks(rgba[:, :200], "agent", scale=1) == []


def test_plant_footprints_requires_one_to_one_public_site_anchors():
    hsv = np.zeros((120, 120, 3), np.uint8)
    hsv[10:30, 10:30] = (30, 100, 210)
    hsv[70:90, 70:90] = (30, 100, 210)
    image = np.dstack([cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR), np.full(hsv.shape[:2], 255, np.uint8)])
    assert set(plant_footprints(image, {"A": (.17, .17), "B": (.67, .67)})) == {
        "A plant footprint", "B plant footprint",
    }
    assert plant_footprints(image, {"A": (.17, .17), "B": (.20, .21)}) == {}
