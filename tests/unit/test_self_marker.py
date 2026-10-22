from __future__ import annotations

import json

import cv2
import numpy as np
import pytest

from valorant_ai_coach.visual.pixels import PixelMeasurementExtractor
from valorant_ai_coach.visual.runtime import load_visual_profile
from valorant_ai_coach.visual.self_marker import SelfMarkerTracker


@pytest.fixture
def marker_case(tmp_path):
    rng = np.random.default_rng(42)
    positive = rng.integers(0, 256, (17, 17, 3), np.uint8)
    negative = rng.integers(0, 256, (17, 17, 3), np.uint8)
    for name, image in (("positive", positive), ("negative", negative)):
        assert cv2.imwrite(str(tmp_path / f"{name}.png"), image)
    spec = {
        "mode": "appearance_v1",
        "positive_templates": [str(tmp_path / "positive.png")],
        "negative_templates": [str(tmp_path / "negative.png")],
    }
    crop = np.full((100, 120, 3), 100, np.uint8)
    crop[30:47, 40:57] = positive
    crop[60:77, 80:97] = negative
    return spec, crop


def test_textured_position_and_contiguous_track_without_identity_promotion(marker_case):
    spec, crop = marker_case
    tracker = SelfMarkerTracker()
    results = [tracker.observe(crop, i*.2, spec, ownership_eligible=True) for i in range(3)]
    assert [r.status for r in results] == ["candidate", "candidate", "tracked"]
    assert results[-1].x_roi_norm == pytest.approx(48/120)
    assert results[-1].y_roi_norm == pytest.approx(38/100)
    assert results[-1].appearance_score == pytest.approx(1, abs=1e-5)
    assert {r.track_id for r in results} == {0}
    assert {r.identity for r in results} == {"UNKNOWN"}
    assert {r.qualification for r in results} == {"development_only"}


def test_duplicate_icons_are_unknown_even_after_tracking(marker_case):
    spec, crop = marker_case
    tracker = SelfMarkerTracker()
    tracker.observe(crop, 0, spec, ownership_eligible=True)
    crop[5:22, 80:97] = crop[30:47, 40:57]
    result = tracker.observe(crop, .2, spec, ownership_eligible=True)
    assert result.reason == "appearance_ambiguous"
    assert result.candidate_count == 2
    assert result.x_roi_norm is None


@pytest.mark.parametrize("time", [0, -.1, .31, 2, float("nan")])
def test_gap_duplicate_and_invalid_time_never_extend_track(marker_case, time):
    spec, crop = marker_case
    tracker = SelfMarkerTracker()
    tracker.observe(crop, 0, spec, ownership_eligible=True)
    result = tracker.observe(crop, time, spec, ownership_eligible=True)
    assert result.status != "tracked"
    if time >= 0:
        assert result.track_id != 0


def test_jump_is_not_interpolated_or_reassigned(marker_case):
    spec, crop = marker_case
    tracker = SelfMarkerTracker()
    tracker.observe(crop, 0, spec, ownership_eligible=True)
    moved = np.full_like(crop, 100)
    moved[30:47, 95:112] = crop[30:47, 40:57]
    result = tracker.observe(moved, .2, spec, ownership_eligible=True)
    assert result.reason == "position_jump"
    assert result.x_roi_norm is None
    assert tracker.observe(moved, .4, spec, ownership_eligible=True).status == "candidate"


def test_blank_color_only_and_nonself_controls_do_not_supply_position(marker_case):
    spec, crop = marker_case
    tracker = SelfMarkerTracker()
    for control in [np.zeros_like(crop), np.full_like(crop, (0, 255, 255))]:
        assert tracker.observe(control, 0, spec, ownership_eligible=True).x_roi_norm is None
    spec["negative_templates"] = spec["positive_templates"]
    result = tracker.observe(crop, 0, spec, ownership_eligible=True)
    assert result.reason == "nonself_not_separated"


@pytest.mark.parametrize("state", ["spectator_first_person", "unknown", "remote_control_view"])
def test_pixel_integration_blocks_nonself_states_and_production_values(marker_case, state):
    spec, crop = marker_case
    profile = {
        "validated": True, "minimap_north_up_calibrated": True,
        "rois": {"minimap": [0, 0, 1, 1]}, "minimap_self_marker": spec,
        # A legacy color proposal cannot bypass the experimental identity boundary.
        "minimap_colors_hsv": {"self": {"lower": [0, 0, 0], "upper": [179, 255, 255]}},
    }
    extractor = PixelMeasurementExtractor()
    hud = {"time_sec": 0, "primary_state": state,
           "values": {"player_specific_hud_valid": True}, "quality": {}}
    result = extractor.measure(crop, None, hud, profile=profile)
    assert result["measurement_meta"]["minimap_self_observation"]["reason"] == "ownership_blocked"
    assert result["minimap"].get("self_x_norm") is None
    assert result["minimap"]["track_confidence"] == 0
    hud["primary_state"] = "live_first_person"
    result = extractor.measure(crop, None, hud, profile=profile)
    assert result["measurement_meta"]["minimap_self_observation"]["x_roi_norm"] is not None
    assert result["minimap"].get("self_x_norm") is None


def test_invalid_profiles_and_shape_change_reset(marker_case, tmp_path):
    spec, crop = marker_case
    tracker = SelfMarkerTracker()
    invalid_result = tracker.observe(crop, 0, {}, ownership_eligible=True)
    assert invalid_result.reason == "invalid_reference_profile"
    flat = tmp_path / "flat.png"
    assert cv2.imwrite(str(flat), np.zeros((17, 17, 3), np.uint8))
    invalid = dict(spec, positive_templates=[str(flat)])
    assert tracker.observe(crop, 0, invalid, ownership_eligible=True).status == "unknown"
    for i in range(3):
        tracker.observe(crop, i*.2, spec, ownership_eligible=True)
    enlarged = np.pad(crop, ((0, 1), (0, 1), (0, 0)))
    assert tracker.observe(enlarged, .6, spec, ownership_eligible=True).status == "candidate"


def test_relative_profile_references_and_asset_fingerprint(marker_case, tmp_path):
    from valorant_ai_coach.events import EventSourceContract
    from valorant_ai_coach.resources import resource_path
    from valorant_ai_coach.visual.runtime import RealVisualAnalyzer

    spec, _ = marker_case
    spec["positive_templates"] = ["positive.png"]
    spec["negative_templates"] = ["negative.png"]
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"minimap_self_marker": spec}), encoding="utf-8")
    profile = load_visual_profile(str(path))
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    analyzer = RealVisualAnalyzer(contract, profile=profile)
    before = analyzer.fingerprint()
    assert cv2.imwrite(str(tmp_path / "positive.png"), np.zeros((17, 17, 3), np.uint8))
    assert analyzer.fingerprint()["contracts"] != before["contracts"]


def test_successful_map_alignment_cannot_promote_experimental_positions(marker_case, tmp_path):
    from valorant_ai_coach.events import EventSourceContract
    from valorant_ai_coach.maps.registry import MapRegistry
    from valorant_ai_coach.resources import resource_path
    from valorant_ai_coach.video import FrameSample
    from valorant_ai_coach.visual.runtime import RealVisualAnalyzer

    spec, crop = marker_case
    definition = MapRegistry().load("summit")
    image = cv2.imread(str(definition.reference_asset))
    image[200:217, 200:217] = crop[30:47, 40:57]
    path = tmp_path / "frame.png"
    assert cv2.imwrite(str(path), image)
    profile = {
        "validated": True, "rois": {"minimap": [0, 0, 1, 1]},
        "minimap_self_marker": spec,
        "map_zone": {"manual_map_id": "summit"},
    }
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    analyzer = RealVisualAnalyzer(contract, profile=profile)
    frames = [FrameSample(i*.2, path) for i in range(4)]
    hud = [{"time_sec": f.time_sec, "primary_state": "live_first_person",
            "values": {"player_specific_hud_valid": True}, "quality": {}}
           for f in frames]
    observations, proofs, _ = analyzer._measure(frames, hud)
    assert proofs[3]["minimap_self_observation"]["status"] == "tracked"
    assert proofs[3]["minimap_self_observation"]["x_roi_norm"] == pytest.approx(208/image.shape[1])
    assert "map_calibration_accepted" in proofs[3]["zone_resolution"]["diagnostics"]
    assert proofs[3]["zone_resolution"]["zone_id"] is None
    assert observations[3]["minimap"]["self_x_norm"] is None
    assert observations[3]["minimap"]["track_confidence"] == 0


def test_missing_player_hud_and_transition_reset_even_matching_appearance(marker_case):
    spec, crop = marker_case
    profile = {"rois": {"minimap": [0, 0, 1, 1]}, "minimap_self_marker": spec}
    extractor = PixelMeasurementExtractor()
    for value, flags in [(False, []), (True, ["visual_transition"]),
                         (True, ["round_end_banner"]), (True, ["buy_phase_banner"])]:
        hud = {"time_sec": 0, "primary_state": "live_first_person",
               "values": {"player_specific_hud_valid": value}, "state_flags": flags}
        result = extractor.measure(crop, None, hud, profile=profile)
        raw = result["measurement_meta"]["minimap_self_observation"]
        assert raw["reason"] == "ownership_blocked"
        assert raw["x_roi_norm"] is None
