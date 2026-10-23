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
    assert {z["zone_id"] for z in definition.data["zones"]} == {
        "bind_a_plant", "bind_b_plant", "bind_defender_spawn_interior", "bind_b_long_interior",
        "bind_b_window_interior", "bind_a_lamps_interior", "bind_a_shower_interior"}
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


def test_partial_interiors_are_inside_public_floor_without_claiming_full_callouts(bind_case):
    registry, definition, _, _, _ = bind_case
    floor = cv2.imread(str(registry.root/"assets/bind_visible_floor.png"), cv2.IMREAD_GRAYSCALE)
    for zone in definition.data["zones"][2:]:
        assert zone["site_id"] is None
        assert zone["geometry_confidence_cap"] == .7
        points = np.array([[round(142+p[0]*819), round(12+p[1]*969)]
                           for p in zone["polygon_norm"]], np.int32)
        support = np.zeros_like(floor)
        cv2.fillPoly(support, [points], 255)
        assert np.all(floor[support > 0] > 0)


def test_private_path_cli_connects_real_cv_frames_to_viewer_without_fact(bind_case, tmp_path):
    from scripts.development_map_path import build

    _, _, frame, profile, _ = bind_case
    image = tmp_path/"synthetic.png"
    assert cv2.imwrite(str(image), frame)
    profile_path = tmp_path/"profile.json"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    manifest = {
        "source_split": "DEVELOPMENT", "qualification": "development_only",
        "source_id": "synthetic", "acquisition_id": "one-window",
        "view_evidence_kind": "source_review", "profile_path": str(profile_path),
        "inspect_reference_appearances": True,
        "observations": [{"image_path": str(image), "time_sec": i*.2, "frame_index": i,
                          "view": {"primary_state": "live_first_person",
                                   "values": {"player_specific_hud_valid": True}}}
                         for i in range(6)],
    }
    path = tmp_path/"manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    result = build(path, tmp_path/"private")
    assert len(result["segments"]) == 1
    assert result["segments"][0]["observed_span_sec"] == pytest.approx(1)
    assert (tmp_path/"private/path_PRIVATE.html").is_file()
    assert result["formal_self_position_fact"] is None
    assert all(p["marker_reference_evidence"]["ownership"] == "UNKNOWN"
               for p in result["samples"])
    manifest["source_split"] = "FINAL_HOLDOUT_CANDIDATE"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="DEVELOPMENT"):
        build(path, tmp_path/"must-not-exist")
    assert not (tmp_path/"must-not-exist").exists()


def test_coarse_patch_keeps_resolver_threshold_and_is_aggregated_separately(bind_case):
    from valorant_ai_coach.visual.development_trajectory import analyze_candidate_path

    registry, definition, _, profile, _ = bind_case
    frame = np.zeros((427, 455, 3), np.uint8)
    frame[9:419, 21:431] = cv2.resize(cv2.imread(str(definition.reference_asset)), (410, 410))
    x, y = round(330*410/1024+21), round(430*410/1024+9)
    frame[y-8:y+9, x-8:x+9] = cv2.imread(profile["minimap_self_marker"]["positive_templates"][0])
    pipeline = DevelopmentMapTimeline(profile, registry=registry,
                                      inspect_reference_appearances=True)
    records = [pipeline.observe(
        frame, i*.2, i, view={"primary_state": "live_first_person",
                              "values": {"player_specific_hud_valid": True}},
        evidence_kind="source_review", source_id="synthetic", acquisition_id="coarse",
    ) for i in range(8)]
    assert all(r["zone_resolution"]["zone_id"] is None for r in records)
    assert records[-1]["zone_resolution"]["resolution_scope"] == "coarse_role"
    assert records[-1]["development_region_candidate"]["geometry_confidence_cap"] == .7
    path = analyze_candidate_path(records, reference_size_px=(819, 969))
    assert path["zone_observation_spans_sec"] == {}
    assert path["region_candidate_observation_spans_sec"] == {
        "bind_b_window_interior": pytest.approx(1.4)}
    blocked = pipeline.observe(
        frame, 1.6, 8, view={"primary_state": "spectator_first_person"},
        evidence_kind="source_review", source_id="synthetic", acquisition_id="coarse",
    )
    assert blocked["marker_reference_evidence"]["matches"]
    assert blocked["map_position_norm"] is None
    assert blocked["development_region_candidate"] is None
    assert blocked["formal_self_position_fact"] is None


def test_separate_inspector_cannot_mix_changed_reference_with_old_position(bind_case, monkeypatch):
    registry, _, frame, profile, _ = bind_case
    pipeline = DevelopmentMapTimeline(profile, registry=registry,
                                      inspect_reference_appearances=True)
    assert pipeline.inspector is not None
    monkeypatch.setattr(pipeline.inspector, "inspect", lambda *args: {
        "reference_fingerprint": "different-content", "matches": [],
        "ownership": "UNKNOWN", "qualification": "development_only"})
    result = pipeline.observe(
        frame, 0, 0, view={"primary_state": "live_first_person",
                          "values": {"player_specific_hud_valid": True}},
        evidence_kind="source_review", source_id="synthetic", acquisition_id="changed-ref",
    )
    assert result["appearance"]["reason"] == "reference_changed_during_observation"
    assert result["map_position_norm"] is None
    assert result["map_segment"] is None
    assert result["development_region_candidate"] is None


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
    synthetic.data["zones"] = synthetic.data["zones"][:2]
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


def test_haven_is_isolated_hashed_and_limited_to_public_shaded_plants():
    import hashlib

    from shapely.geometry import Polygon

    from valorant_ai_coach.visual.development_map import development_registry

    registry = development_registry('haven')
    definition = registry.load('haven')
    provenance = json.loads((registry.root/'provenance.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(definition.reference_asset.read_bytes()).hexdigest() == (
        provenance['reference_sha256'])
    floor = registry.root/provenance['visible_floor_asset']
    assert hashlib.sha256(floor.read_bytes()).hexdigest() == provenance['visible_floor_sha256']
    transform = provenance['reference_authoring_transform']
    assert transform['runtime_dynamic_rotation_supported'] is False
    assert {z['zone_id'] for z in definition.data['zones']} == {
        'haven_a_plant', 'haven_b_plant', 'haven_c_plant'}
    assert all(Polygon(z['polygon_norm']).is_valid for z in definition.data['zones'])
    assert definition.callouts['records'] == {} and definition.data['topology_edges'] == []
    assert registry.registry['maps']['haven']['production'] is False
    with pytest.raises(KeyError):
        MapRegistry().select(manual_map_id='haven')
    with pytest.raises(ValueError):
        development_registry('lotus')
    with pytest.raises(MapRegistryError):
        MapRegistry(registry.root)


def test_configured_veto_breaks_track_even_with_live_upstream_view(bind_case, tmp_path):
    _, _, frame, profile, _ = bind_case
    timeline = DevelopmentMapTimeline(profile)
    view = {'primary_state': 'live_first_person', 'values': {'player_specific_hud_valid': True}}

    def observe(t):
        return timeline.observe(frame, t, round(t*5), view=view, evidence_kind='source_review',
                                source_id='synthetic', acquisition_id='same')

    before = observe(0)
    assert before['map_position_norm'] is not None
    glyph = frame[30:55, 100:261].copy()
    path = tmp_path/'switch.png'
    cv2.imwrite(str(path), glyph)
    profile['development_view_veto'] = {
        'mode': 'spectator_switch_v1', 'template_path': str(path),
        'reference_frame_size_px': [455, 427], 'roi': [90/455, 20/427, 270/455, 65/427]}
    blocked = observe(.2)
    assert blocked['development_view_veto']['status'] == 'spectator_ui'
    assert blocked['ownership']['observed_view'] == 'live_first_person'
    assert blocked['ownership']['view_eligible'] is False
    assert blocked['map_position_norm'] is None and blocked['map_segment'] is None
    assert blocked['appearance']['reason'] == 'ownership_blocked'
    assert blocked['development_events'] == []
    profile.pop('development_view_veto')
    resumed = observe(.4)
    assert resumed['map_segment'] != before['map_segment']
    assert resumed['formal_self_position_fact'] is None


def test_invalid_boundary_assumption_resets_state(bind_case):
    _, _, frame, profile, _ = bind_case
    timeline = DevelopmentMapTimeline(profile)
    view = {'primary_state': 'live_first_person', 'values': {'player_specific_hud_valid': True}}

    def observe(t):
        return timeline.observe(frame, t, round(t*5), view=view, evidence_kind='source_review',
                                source_id='synthetic', acquisition_id='same')

    old = observe(0)
    profile['map_zone']['candidate_error_radius_reference_px'] = -1
    with pytest.raises(ValueError):
        observe(.2)
    assert timeline.previous is None and timeline.segment is None
    profile['map_zone'].pop('candidate_error_radius_reference_px')
    assert observe(.4)['map_segment'] != old['map_segment']


def test_haven_fixed_outline_roundtrip_and_wrong_map_rejection():
    from valorant_ai_coach.visual.development_map import development_registry

    definition = development_registry('haven').load('haven')
    source = cv2.imread(str(definition.reference_asset))
    frame = np.zeros((427, 455, 3), np.uint8)
    frame[9:419, 21:431] = cv2.resize(source, (410, 410), interpolation=cv2.INTER_AREA)
    calibrator = OutlineMinimapCalibrator()
    result = calibrator.analyze(frame, [0, 0, 1, 1], definition)
    assert result.status == 'ok'
    x0, y0, x1, y1 = definition.data['coordinate_system'][
        'reference_map_mask_bbox_within_roi_px']
    for x, y in [(173, 611), (513, 612), (841, 595)]:
        actual = result.transform((21+x*410/1024)/455, (9+y*410/1024)/427)
        assert actual == pytest.approx(((x-x0)/(x1-x0), (y-y0)/(y1-y0)), abs=.008)
    wrong = calibrator.analyze(frame, [0, 0, 1, 1], bind_development_registry().load('bind'))
    assert wrong.status != 'ok'


def test_independent_context_contradiction_and_reference_change_break_path(bind_case, tmp_path):
    _, _, frame, profile, _ = bind_case
    glyph = frame[30:55, 100:261].copy()
    path = tmp_path/'context.png'
    cv2.imwrite(str(path), glyph)
    # Use a resized synthetic full frame so a reviewed slot can be disjoint from the map.
    full = np.zeros((854, 455, 3), np.uint8)
    full[:427] = frame
    full[600:625, 100:261] = glyph
    profile['rois']['minimap'] = [0, 0, 1, .5]
    profile['development_ownership_evidence'] = {
        'mode': 'screen_context_v1', 'frame_size_px': [455, 854],
        'slot_review': 'source_reviewed_not_qualified', 'probes': [{
            'claim': 'first_person_hud', 'template_path': str(path),
            'roi': [90/455, 590/854, 270/455, 635/854]}]}
    pipeline = DevelopmentMapTimeline(profile)
    view = {'primary_state': 'live_first_person', 'values': {'player_specific_hud_valid': True}}

    def observe(t):
        return pipeline.observe(full, t, round(t*5), view=view, evidence_kind='source_review',
                                source_id='synthetic', acquisition_id='same')

    before = observe(0)
    assert before['map_position_norm'] is not None
    assert before['ownership']['identity'] == 'UNKNOWN'
    cv2.imwrite(str(path), np.random.default_rng(89).integers(0, 256, glyph.shape, np.uint8))
    after = observe(.2)
    assert after['map_segment'] != before['map_segment']
    assert after['context_sha256'] != before['context_sha256']
    cv2.imwrite(str(path), glyph)
    profile['development_ownership_evidence']['probes'][0]['claim'] = 'death_report'
    blocked = observe(.4)
    assert blocked['ownership_evidence']['declared_view_conflict'] is True
    assert blocked['map_position_norm'] is None
    assert blocked['development_events'] == []
    assert blocked['formal_self_position_fact'] is None


def test_reusable_benchmark_freezes_inputs_and_blind_review_packet(bind_case, tmp_path):
    import hashlib

    from scripts.development_map_benchmark import build

    _, _, frame, profile, _ = bind_case
    image = tmp_path/'frame.png'
    cv2.imwrite(str(image), frame)
    profile_path = tmp_path/'profile.json'
    profile_path.write_text(json.dumps(profile), encoding='utf-8')
    manifest = {'source_split': 'DEVELOPMENT', 'exposure': 'DEVELOPMENT',
                'qualification': 'development_only', 'source_id': 'synthetic',
                'acquisition_id': 'native-window', 'native_time_base': '1/5',
                'baseline_profile_path': str(profile_path),
                'variant_profile_path': str(profile_path),
                'view_evidence_kind': 'source_review', 'observations': [{
                    'image_path': str(image),
                    'image_sha256': hashlib.sha256(image.read_bytes()).hexdigest(),
                    'pts_tick': i, 'time_sec': i*.2, 'frame_index': i,
                    'view': {'primary_state': 'live_first_person',
                             'values': {'player_specific_hud_valid': True}}} for i in range(3)]}
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    result = build(path, tmp_path/'private')
    assert result['summary']['baseline']['map_candidates'] == 3
    assert result['summary']['variant']['formal_outputs'] == 0
    packet = json.loads((tmp_path/'private/review_packet_PRIVATE.json').read_text(encoding='utf-8'))
    assert packet['prediction_positions_prefilled'] is False
    assert len(packet['reviews']) == 3
    assert all(r['status'] == 'pending' and r['center_roi_px'] is None for r in packet['reviews'])
    from scripts.development_map_benchmark import apply_reviews

    packet['reviews'][0].update(
        status='human_confirmed', role='SELF', source_tolerance_px=2, reference_tolerance_px=2,
        center_roi_px=[200, 200], landmark_roi_px=[[10, 10], [400, 10], [10, 400]],
        landmark_reference_px=[[0, 0], [1024, 0], [0, 1024]])
    reviews_path = tmp_path/'reviews.json'
    reviews_path.write_text(json.dumps(packet), encoding='utf-8')
    source = tmp_path/'private/variant_observations_PRIVATE.json'
    frozen_bytes = source.read_bytes()
    reviewed = apply_reviews(source, reviews_path, tmp_path/'reviewed')
    assert len(reviewed['comparisons']) == 1
    assert reviewed['trajectory']['coordinate_review_coverage'][
        'reviewed_position_observations'] == 1
    assert source.read_bytes() == frozen_bytes
    assert reviewed['qualification_or_error_bound_established'] is False
    with pytest.raises(ValueError, match='fresh private directory'):
        apply_reviews(source, reviews_path, tmp_path/'reviewed')
    manifest['observations'][1]['pts_tick'] = 999
    path.write_text(json.dumps(manifest), encoding='utf-8')
    with pytest.raises(ValueError, match='tick/time'):
        build(path, tmp_path/'invalid')
