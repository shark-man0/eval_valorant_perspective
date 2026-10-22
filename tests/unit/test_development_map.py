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
    results = [timeline.observe(frame, i*.2, i, view=view, evidence_kind="source_review",
                                source_id="synthetic", acquisition_id="test")
               for i in range(8)]
    assert results[-1]["map_position_norm"] is not None
    assert results[-1]["zone_resolution"]["zone_id"] == "bind_a_plant"
    assert {r["map_segment"] for r in results} == {0}
    assert all(r["ownership"]["identity"] == "UNKNOWN" for r in results)
    assert all(r["formal_self_position_fact"] is None for r in results)
    assert all(r["qualification"] == "development_only" for r in results)
    # A real source-time gap must start a fresh segment and fresh zone dwell.
    resumed = timeline.observe(frame, 4, 10, view=view, evidence_kind="source_review",
                               source_id="synthetic", acquisition_id="test")
    assert resumed["map_segment"] == 1
    assert resumed["zone_resolution"]["zone_id"] is None
    assert resumed["map_speed_norm_per_sec"] is None
    blocked = timeline.observe(
        frame, 4.2, 11, view={"primary_state": "spectator_first_person"},
        evidence_kind="source_review", source_id="synthetic", acquisition_id="test",
    )
    assert blocked["map_position_norm"] is None
    reappeared = timeline.observe(
        frame, 4.4, 12, view=view, evidence_kind="source_review",
        source_id="synthetic", acquisition_id="test",
    )
    assert reappeared["appearance"]["status"] == "candidate"
    assert reappeared["map_segment"] != resumed["map_segment"]


def test_spectator_and_buy_views_cannot_be_attributed_to_self(bind_case):
    registry, _, frame, profile, _ = bind_case
    timeline = DevelopmentMapTimeline(profile, registry=registry)
    for i, state in enumerate(["unknown", "spectator_first_person", "remote_control_view"]):
        result = timeline.observe(
            frame, i*.2, i, view={"primary_state": state,
                                "values": {"player_specific_hud_valid": True}},
            evidence_kind="unqualified_hud_observation",
            source_id="synthetic", acquisition_id="test",
        )
        assert result["map_position_norm"] is None
        assert result["zone_resolution"]["zone_id"] is None
        assert result["development_events"] == []
    result = timeline.observe(
        frame, .8, 4, view={"primary_state": "live_first_person",
                          "values": {"player_specific_hud_valid": True},
                          "state_flags": ["buy_phase_banner"]}, evidence_kind="source_review",
        source_id="synthetic", acquisition_id="test",
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
        timeline.observe(frame, 0, 0, view={}, evidence_kind="inferred_from_marker",
                         source_id="synthetic", acquisition_id="test")


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


def test_unknown_owner_zone_transition_never_emits_player_contract(bind_case, monkeypatch):
    from valorant_ai_coach.maps.resolver import ZoneResolver

    registry, definition, frame, profile, (x, y) = bind_case
    profile["validated"] = True  # Cannot authorize ownership or formal events.
    synthetic = copy.deepcopy(definition)
    # Synthetic adjacent zones within visible floor, never registered geometry.
    for zone, left, right in zip(synthetic.data["zones"], [.66, .73], [.73, .81], strict=True):
        zone["polygon_norm"] = [[left, .30], [right, .30], [right, .39], [left, .39]]
    timeline = DevelopmentMapTimeline(profile, registry=registry)
    timeline.timeline.definition = synthetic
    immediate = copy.deepcopy(registry.runtime)
    # Adversarial resolved-zone seam; production debounce is never changed.
    immediate["temporal_debounce"]["zone_transition_persistence_sec"] = 0
    timeline.resolver = ZoneResolver(synthetic, immediate)
    calibration = timeline.timeline.calibrate(frame)
    monkeypatch.setattr(timeline.timeline, "calibrate", lambda _: calibration)
    portrait = frame[y-8:y+9, x-8:x+9].copy()
    background = frame.copy()
    background[y-8:y+9, x-8:x+9] = 0
    view = {"primary_state": "live_first_person", "values": {"player_specific_hud_valid": True}}
    results = []
    for i in range(24):
        image = background.copy()
        px, py = round((700 if i < 12 else 760)*410/1024+21), round(360*410/1024+9)
        image[py-8:py+9, px-8:px+9] = portrait
        results.append(timeline.observe(image, i*.2, i, view=view, evidence_kind="source_review",
                                        source_id="synthetic", acquisition_id="test"))
    assert len({r["zone_resolution"]["zone_id"] for r in results} - {None}) == 2
    events = [e for r in results for e in r["development_events"]]
    assert not any(e.get("actor") == "player" or "type" in e for e in events)
    assert any(e.get("candidate_kind") == "zone_transition" for e in events)
    assert all(e["ownership"] == "UNKNOWN" and e["qualification"] == "development_only"
               for e in events)
    assert all(r["formal_self_position_fact"] is None for r in results)
    from jsonschema import Draft202012Validator

    from valorant_ai_coach.visual.map_consumer import MapEventConsumer

    consumer = MapEventConsumer(synthetic, registry.runtime)
    validator = Draft202012Validator(registry.schemas["resolution"])
    for result in results:
        resolution = result["zone_resolution"]
        assert resolution["qualification"] == "development_only"
        assert resolution["ownership"] == "UNKNOWN"
        assert not validator.is_valid(resolution)
        assert consumer.consume(resolution) == []


@pytest.mark.parametrize("scale,offset", [(.36, (60, 30)), (.40, (35, 15)), (.43, (30, 5))])
def test_cached_grid_matches_fresh_search_and_known_geometry(bind_case, scale, offset):
    from dataclasses import asdict

    _, definition, _, _, _ = bind_case
    reference = cv2.imread(str(definition.reference_asset))
    x0, y0, _, _ = definition.data["coordinate_system"][
        "reference_map_mask_bbox_within_roi_px"
    ]
    matrix = np.array([[scale, 0, offset[0]-x0*scale],
                       [0, scale, offset[1]-y0*scale]], np.float32)
    frame = cv2.warpAffine(reference, matrix, (455, 427))
    cached = OutlineMinimapCalibrator()
    fresh = OutlineMinimapCalibrator(cache_reference=False)
    cold = cached.analyze(frame, [0, 0, 1, 1], definition)
    warm = cached.analyze(frame, [0, 0, 1, 1], definition)
    uncached = fresh.analyze(frame, [0, 0, 1, 1], definition)
    assert cold.status == "ok"
    assert asdict(cold) == asdict(warm) == asdict(uncached)
    assert cached._outline_feature_bytes <= 64*2**20
    # A different current frame cannot inherit the successful transform.
    rejected = cached.analyze(np.zeros_like(frame), [0, 0, 1, 1], definition)
    assert rejected.status != "ok"
    assert rejected.transform(.5, .5) is None


def test_acquisition_profile_and_roi_changes_reset_paths(bind_case):
    registry, _, frame, profile, _ = bind_case
    timeline = DevelopmentMapTimeline(profile, registry=registry)
    view = {"primary_state": "live_first_person", "values": {"player_specific_hud_valid": True}}
    def observe(t, *, source="one", acquisition="one"):
        return timeline.observe(frame, t, round(t*5), view=view, evidence_kind="source_review",
                                source_id=source, acquisition_id=acquisition)
    initial = observe(0)
    assert observe(.2)["map_segment"] == initial["map_segment"]
    changed = observe(.4, acquisition="cut")
    assert changed["map_segment"] != initial["map_segment"]
    assert changed["appearance"]["status"] == "candidate"
    assert changed["zone_resolution"]["zone_id"] is None
    another = observe(.6, source="two", acquisition="cut")
    assert another["map_segment"] != changed["map_segment"]
    profile["rois"]["minimap"] = [.001, 0, 1, 1]
    changed_roi = observe(.8, source="two", acquisition="cut")
    assert changed_roi["appearance"]["status"] == "candidate"
    assert changed_roi["development_events"] == []


def test_invalid_observation_discards_previous_state(bind_case):
    registry, _, frame, profile, _ = bind_case
    timeline = DevelopmentMapTimeline(profile, registry=registry)
    view = {"primary_state": "live_first_person", "values": {"player_specific_hud_valid": True}}
    args = {"view": view, "source_id": "source", "acquisition_id": "acquisition"}
    first = timeline.observe(frame, 0, 0, evidence_kind="source_review", **args)
    with pytest.raises(ValueError):
        timeline.observe(frame, .1, 1, evidence_kind="invalid", **args)
    resumed = timeline.observe(frame, .2, 2, evidence_kind="source_review", **args)
    assert resumed["appearance"]["track_id"] != first["appearance"]["track_id"]
    assert resumed["map_segment"] != first["map_segment"]


def test_cached_reference_is_hashed_and_new_roi_grid_is_recomputed(bind_case, tmp_path):
    import hashlib
    from dataclasses import asdict

    _, definition, frame, _, _ = bind_case
    definition = copy.deepcopy(definition)
    content = definition.reference_asset.read_bytes()
    definition.reference_asset = tmp_path/"reference.png"
    definition.reference_asset.write_bytes(content)
    cached = OutlineMinimapCalibrator(expected_reference_sha256=hashlib.sha256(content).hexdigest())
    assert cached.analyze(frame, [0, 0, 1, 1], definition).status == "ok"
    padded = np.pad(frame, ((0, 8), (0, 8), (0, 0)))
    recomputed = cached.analyze(padded, [0, 0, 1, 1], definition)
    fresh = OutlineMinimapCalibrator(cache_reference=False).analyze(
        padded, [0, 0, 1, 1], definition,
    )
    assert asdict(recomputed) == asdict(fresh)
    definition.reference_asset.write_bytes(b"changed asset")
    rejected = cached.analyze(frame, [0, 0, 1, 1], definition)
    assert rejected.diagnostics == ("reference_asset_hash_mismatch",)
    assert cached.transform(.5, .5) is None


def test_changed_map_selection_cannot_keep_old_bind_transform(bind_case):
    registry, _, frame, profile, _ = bind_case
    timeline = DevelopmentMapTimeline(profile, registry=registry)
    view = {"primary_state": "live_first_person", "values": {"player_specific_hud_valid": True}}
    args = {"view": view, "source_id": "source", "acquisition_id": "acquisition",
            "evidence_kind": "source_review"}
    assert timeline.observe(frame, 0, 0, **args)["map_position_norm"] is not None
    profile["map_zone"] = {"manual_map_id": "unregistered"}
    with pytest.raises(ValueError, match="Map selection"):
        timeline.observe(frame, .2, 1, **args)
