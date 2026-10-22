from __future__ import annotations

import copy
import json
import shutil

import cv2
import numpy as np
import pytest

from valorant_ai_coach.maps.outline_calibration import OutlineMinimapCalibrator
from valorant_ai_coach.maps.registry import MapRegistry, MapRegistryError
from valorant_ai_coach.visual.development_map import (
    DevelopmentMapTimeline,
    bind_development_registry,
)
from valorant_ai_coach.visual.self_marker import SelfMarkerTracker


@pytest.fixture(scope="module", autouse=True)
def bounded_opencv():
    old = cv2.getNumThreads()
    cv2.setNumThreads(1)
    yield
    cv2.setNumThreads(old)


@pytest.fixture
def bind_case(tmp_path):
    registry = bind_development_registry()
    definition = registry.load("bind")
    reference = cv2.imread(str(definition.reference_asset))
    frame = np.zeros((427, 455, 3), np.uint8)
    frame[9:419, 21:431] = cv2.resize(reference, (410, 410), interpolation=cv2.INTER_AREA)
    rng = np.random.default_rng(87)
    portrait = rng.integers(0, 256, (17, 17, 3), dtype=np.uint8)
    nonself = rng.integers(0, 256, (17, 17, 3), dtype=np.uint8)
    x, y = round(730*410/1024+21), round(340*410/1024+9)
    frame[y-8:y+9, x-8:x+9] = portrait
    for name, image in [("portrait", portrait), ("nonself", nonself)]:
        assert cv2.imwrite(str(tmp_path/f"{name}.png"), image)
    profile = {
        "map_zone": {"manual_map_id": "bind"}, "rois": {"minimap": [0, 0, 1, 1]},
        "reference_identity_confirmed": True,
        "minimap_self_marker": {
            "mode": "portrait_v2", "positive_templates": [str(tmp_path/"portrait.png")],
            "negative_templates": [str(tmp_path/"nonself.png")],
        },
    }
    return registry, definition, frame, profile, (x, y)


def test_registered_public_geometry_is_limited_and_not_default_production(bind_case):
    registry, definition, _, _, _ = bind_case
    assert registry.registry["maps"]["bind"]["production"] is False
    assert {z["zone_id"] for z in definition.data["zones"]} == {"bind_a_plant", "bind_b_plant"}
    assert definition.data["topology_edges"] == []
    assert definition.callouts["records"] == {}
    assert json.loads((registry.root/"provenance.json").read_text(encoding="utf-8"))[
        "semantic_review"
    ]["recognition_qualification"] is False
    with pytest.raises(KeyError):
        MapRegistry().select(manual_map_id="bind")
    with pytest.raises(MapRegistryError):
        MapRegistry(registry.root)  # Cannot silently activate via ordinary custom-root API.
    assert registry.runtime == MapRegistry().runtime


def test_whole_outline_calibration_recovers_known_synthetic_transform(bind_case):
    _, definition, frame, _, point = bind_case
    calibrator = OutlineMinimapCalibrator()
    result = calibrator.analyze(frame, [0, 0, 1, 1], definition)
    assert result.status == "ok"
    transformed = result.transform(point[0]/455, point[1]/427)
    x0, y0, x1, y1 = definition.data["coordinate_system"][
        "reference_map_mask_bbox_within_roi_px"
    ]
    expected = ((730-x0)/(x1-x0), (340-y0)/(y1-y0))
    assert transformed == pytest.approx(expected, abs=.004)
    assert calibrator.transform(point[0]/455, point[1]/427) == pytest.approx(transformed, abs=1e-6)
    assert "client_build_unverified" in result.diagnostics


@pytest.mark.parametrize("kind", ["blank", "noise", "grid", "cropped", "rotated", "skewed"])
def test_outline_calibration_rejects_missing_or_wrong_geometry(bind_case, kind):
    _, definition, frame, _, _ = bind_case
    h, w = frame.shape[:2]
    if kind == "blank":
        frame[:] = 127
    elif kind == "noise":
        frame = np.random.default_rng(7).integers(0, 256, frame.shape, dtype=np.uint8)
    elif kind == "grid":
        frame[:] = 0
        frame[::12] = 255
        frame[:, ::12] = 255
    elif kind == "cropped":
        frame[h//2:] = 0
    elif kind == "rotated":
        frame = cv2.warpAffine(frame, cv2.getRotationMatrix2D((w/2, h/2), 12, 1), (w, h))
    else:
        frame = cv2.warpAffine(frame, np.array([[1.15, 0, -30], [0, 1, 0]], np.float32), (w, h))
    result = OutlineMinimapCalibrator().analyze(frame, [0, 0, 1, 1], definition)
    assert result.status != "ok", (kind, result.diagnostics)
    assert result.transform(.5, .5) is None


def test_two_matching_map_instances_are_ambiguous(bind_case):
    _, definition, frame, _, _ = bind_case
    duplicate = np.zeros((427, 920, 3), np.uint8)
    duplicate[:, :455] = duplicate[:, 465:] = frame
    result = OutlineMinimapCalibrator().analyze(duplicate, [0, 0, 1, 1], definition)
    assert result.status != "ok"
    assert "outline_alignment_ambiguous" in result.diagnostics


def test_wrong_registered_reference_does_not_align(bind_case):
    _, definition, _, _, _ = bind_case
    wrong = cv2.imread(str(MapRegistry().load("summit").reference_asset))
    result = OutlineMinimapCalibrator().analyze(wrong, [0, 0, 1, 1], definition)
    assert result.status != "ok"


def test_development_real_cv_flows_to_zone_without_self_fact(bind_case):
    registry, _, frame, profile, _ = bind_case
    timeline = DevelopmentMapTimeline(profile, registry=registry)
    view = {"primary_state": "live_first_person", "values": {"player_specific_hud_valid": True}}
    results = [timeline.observe(frame, i*.2, i, view=view, evidence_kind="source_review")
               for i in range(8)]
    assert results[-1]["map_position_norm"] is not None
    assert results[-1]["zone_resolution"]["zone_id"] == "bind_a_plant"
    assert {r["map_segment"] for r in results} == {0}
    assert all(r["ownership"]["identity"] == "UNKNOWN" for r in results)
    assert all(r["formal_self_position_fact"] is None for r in results)
    assert all(r["qualification"] == "development_only" for r in results)
    # A real source-time gap must start a fresh segment and fresh zone dwell.
    resumed = timeline.observe(frame, 4, 10, view=view, evidence_kind="source_review")
    assert resumed["map_segment"] == 1
    assert resumed["zone_resolution"]["zone_id"] is None
    assert resumed["map_speed_norm_per_sec"] is None


def test_spectator_and_buy_views_cannot_be_attributed_to_self(bind_case):
    registry, _, frame, profile, _ = bind_case
    timeline = DevelopmentMapTimeline(profile, registry=registry)
    for i, state in enumerate(["unknown", "spectator_first_person", "remote_control_view"]):
        result = timeline.observe(
            frame, i*.2, i, view={"primary_state": state,
                                "values": {"player_specific_hud_valid": True}},
            evidence_kind="unqualified_hud_observation",
        )
        assert result["map_position_norm"] is None
        assert result["zone_resolution"]["zone_id"] is None
        assert result["development_events"] == []
    result = timeline.observe(
        frame, .8, 4, view={"primary_state": "live_first_person",
                          "values": {"player_specific_hud_valid": True},
                          "state_flags": ["buy_phase_banner"]}, evidence_kind="source_review",
    )
    assert result["map_position_norm"] is None


def test_floor_asset_hash_and_explicit_view_provenance_are_required(bind_case, tmp_path):
    registry, _, frame, profile, _ = bind_case
    root = tmp_path/"bundle"
    shutil.copytree(registry.root, root)
    (root/"assets/bind_visible_floor.png").write_bytes(b"invalid")
    broken = MapRegistry(root, schema_root=MapRegistry().root/"schemas")
    with pytest.raises(MapRegistryError, match="hash mismatch"):
        DevelopmentMapTimeline(profile, registry=broken)
    timeline = DevelopmentMapTimeline(profile, registry=registry)
    with pytest.raises(ValueError, match="view evidence"):
        timeline.observe(frame, 0, 0, view={}, evidence_kind="inferred_from_marker")


def test_portrait_core_tolerates_external_wedge_change_but_not_duplicate(bind_case):
    _, _, frame, profile, (x, y) = bind_case
    changed = frame.copy()
    patch = changed[y-8:y+9, x-8:x+9]
    yy, xx = np.mgrid[:17, :17]
    patch[(xx-8)**2+(yy-8)**2 > 36] = (0, 255, 255)
    spec = profile["minimap_self_marker"]
    result = SelfMarkerTracker().observe(changed, 0, spec, ownership_eligible=True)
    assert result.x_roi_norm == pytest.approx(x/455)
    assert result.appearance_score > .99
    duplicate = copy.deepcopy(changed)
    duplicate[20:37, 20:37] = patch
    result = SelfMarkerTracker().observe(duplicate, 0, spec, ownership_eligible=True)
    assert result.reason == "appearance_ambiguous"
    assert result.identity == "UNKNOWN"
