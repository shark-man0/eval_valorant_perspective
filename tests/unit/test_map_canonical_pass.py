"""Map observations measured on the canonical samples bind exactly to the timeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.map_canonical_pass import (
    RIM_METHOD,
    RING_METHOD,
    FrameInput,
    RegistrationModes,
    build_report,
    measure_frame,
    own_live_samples,
)
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline

SOURCE = "a" * 64
ATLAS_SHA = "e" * 64
GOLD = (175, 235, 245)
# Reference (1024 px) -> minimap ROI: 0.4 scale, a quarter turn and an offset, like the
# placements measured on real recordings.
TURN = np.array([[0.0, -0.4, 430.0], [0.4, 0.0, 16.0], [0.0, 0.0, 1.0]])
STRAIGHT = np.array([[0.4, 0.0, 20.0], [0.0, 0.4, 10.0], [0.0, 0.0, 1.0]])


def _state(value: str, status: str = "OBSERVED") -> dict[str, Any]:
    return {"value": value, "status": status}


def _sample(second: int) -> dict[str, Any]:
    return freeze_native_sample({
        "source_id": "rec", "source_sha256": SOURCE, "acquisition_id": "canonical",
        "native_epoch": "canonical", "native_pts_tick": second * 15360,
        "native_time_base": "1/15360", "acquired_frame_sha256": f"{second + 1:064x}",
        "native_pixel_sha256": f"{second + 100:064x}", "frame_size_px": [1920, 1080],
    })


def _timeline(n: int = 6) -> dict[str, Any]:
    seconds, frames = [], {}
    for second in range(n):
        sample = _sample(second)
        key = sample["sample_sha256"]
        camera, life = ("SPECTATOR", "DEAD") if second == 3 else ("SELF", "ALIVE")
        seconds.append({"timestamp": second, "sample_refs": [key],
                        "camera_state": _state(camera), "life_state": _state(life)})
        frames[key] = {"sample": sample, "camera": {"value": camera}, "life": {"value": life}}
    return {"version": "development_application_timeline_v1",
            "qualification": "development_only", "formal_outputs": 0,
            "source": {"source_sha256": SOURCE}, "seconds": seconds, "native_frames": frames}


def _atlas() -> np.ndarray:
    atlas = np.zeros((1024, 1024, 4), np.uint8)
    cv2.rectangle(atlas, (100, 100), (900, 300), (150, 150, 150, 255), -1)
    cv2.rectangle(atlas, (400, 300), (600, 950), (150, 150, 150, 255), -1)
    return atlas


def _roi(matrix: np.ndarray, marker_reference: tuple[float, float] | None) -> np.ndarray:
    roi = np.full((427, 455, 3), (70, 30, 80), np.uint8)
    floor = cv2.warpPerspective(_atlas()[:, :, 3], matrix, (455, 427), flags=cv2.INTER_NEAREST)
    roi[floor > 0] = (150, 150, 150)
    if marker_reference is not None:
        point = matrix @ np.array([*marker_reference, 1.0])
        center = (int(round(point[0])), int(round(point[1])))
        cv2.circle(roi, center, 8, GOLD, 3)
        rng = np.random.default_rng(7)
        x, y = center
        roi[y - 3:y + 4, x - 3:x + 4] = rng.integers(40, 200, (7, 7, 3), dtype=np.uint8)
    return roi


def _modes() -> RegistrationModes:
    fits = [TURN + np.eye(3) * 1e-4 * i for i in range(6)] + [STRAIGHT] * 6
    return RegistrationModes.from_fits("map-1", ATLAS_SHA, _atlas(), fits)


def test_registration_modes_choose_the_placement_seen_in_the_canonical_floor() -> None:
    modes = _modes()
    assert len(modes.modes) == 2
    chosen = modes.verify(_roi(TURN, None))
    assert chosen is not None and np.allclose(modes.modes[chosen[0]], TURN, atol=1e-3)
    blank = np.full((427, 455, 3), (70, 30, 80), np.uint8)
    assert modes.verify(blank) is None


def test_only_frames_with_self_alive_on_both_sides_are_read() -> None:
    timeline = _timeline()
    own = own_live_samples(timeline)
    # Second 3 is spectating; seconds 2 and 3 lose their bracket; the last has none.
    assert sorted(own.values()) == [0, 1, 4]


def _inputs(timeline: dict[str, Any], *, library: bool) -> dict[str, FrameInput]:
    items = {}
    for key, second in own_live_samples(timeline).items():
        roi = _roi(TURN, (500.0 + 10 * second, 600.0))
        points = ({"kind": "selected", "map_id": "map-1", "reference_sha256": ATLAS_SHA,
                   "map_reference_px": [500.0 + 10 * second, 600.0]},) if library else ()
        items[key] = FrameInput(timeline["native_frames"][key]["sample"], roi,
                                hashlib.sha256(roi.tobytes()).hexdigest(), None, points)
    return items


def test_report_binds_exactly_through_the_unchanged_loader(tmp_path: Path) -> None:
    timeline = _timeline()
    timeline_path = tmp_path / "timeline_PRIVATE.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    sha = hashlib.sha256(timeline_path.read_bytes()).hexdigest()
    modes = _modes()
    records = {key: measure_frame(item, modes)
               for key, item in _inputs(timeline, library=True).items()}
    assert all(r["chosen"]["methods_agreeing"] == sorted([RING_METHOD, RIM_METHOD])
               for r in records.values())
    report = build_report(timeline, sha, records, modes, receipt_sha256="9" * 64,
                          provenance={"recording_id": "rec"})
    report_path = tmp_path / "map_canonical_PRIVATE.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")
    loaded = load_map_timeline(report_path, timeline_path, timeline)
    assert loaded["summary"]["seconds_with_position"] == 3
    assert loaded["formal_outputs"] == 0
    point = report["segments"][0][0]
    assert point["qualified"] is False and point["position_authority"] is False
    assert point["map_reference_px"] == pytest.approx([500.0, 600.0], abs=1.5)


def test_ring_alone_fills_a_frame_without_a_library_point() -> None:
    timeline = _timeline()
    modes = _modes()
    records = {key: measure_frame(item, modes)
               for key, item in _inputs(timeline, library=False).items()}
    assert {r["chosen"]["method"] for r in records.values()} == {RING_METHOD}


def test_disagreeing_methods_abstain_and_changed_pixels_are_rejected() -> None:
    timeline = _timeline()
    modes = _modes()
    key, item = next(iter(_inputs(timeline, library=True).items()))
    far = ({**item.library_points[0], "map_reference_px": [200.0, 200.0]},)
    roi = item.roi.copy()
    cv2.circle(roi, tuple(int(v) for v in (TURN @ np.array([200.0, 200.0, 1.0]))[:2]),
               8, GOLD, 3)
    moved = FrameInput(item.sample, roi, hashlib.sha256(roi.tobytes()).hexdigest(), None, far)
    record = measure_frame(moved, modes)
    assert record["chosen"] is None
    tampered = FrameInput(item.sample, roi, item.roi_pixel_sha256, None, ())
    with pytest.raises(ValueError, match="changed"):
        measure_frame(tampered, modes)


def test_a_ring_off_the_walkable_floor_is_not_read_as_the_recorder() -> None:
    timeline = _timeline()
    modes = _modes()
    key, item = next(iter(_inputs(timeline, library=False).items()))
    roi = np.full((427, 455, 3), (70, 30, 80), np.uint8)
    floor = cv2.warpPerspective(_atlas()[:, :, 3], TURN, (455, 427), flags=cv2.INTER_NEAREST)
    roi[floor > 0] = (150, 150, 150)
    # (950, 950) on the reference lies well outside both floor rectangles.
    point = TURN @ np.array([950.0, 950.0, 1.0])
    center = (int(round(point[0])), int(round(point[1])))
    cv2.circle(roi, center, 8, GOLD, 3)
    rng = np.random.default_rng(3)
    roi[center[1] - 3:center[1] + 4, center[0] - 3:center[0] + 4] = rng.integers(
        40, 200, (7, 7, 3), dtype=np.uint8)
    moved = FrameInput(item.sample, roi, hashlib.sha256(roi.tobytes()).hexdigest())
    record = measure_frame(moved, modes)
    assert record["ring"]["status"] == "UNIQUE" and record["ring"]["off_floor"] is True
    assert record["chosen"] is None
    assert record["verification"] == "native_frame_pixels"
