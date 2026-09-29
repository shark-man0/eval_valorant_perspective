"""Canonical validator plus real resolver -> Visual -> v3 package integration."""

import json
import subprocess
import sys
from copy import deepcopy

import cv2
import pytest
from shapely.geometry import Polygon

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.hud.models import HudObservationV2, empty_hud_quality, empty_hud_values
from valorant_ai_coach.maps.calibration import CalibrationResult
from valorant_ai_coach.maps.registry import MapRegistry
from valorant_ai_coach.maps.resolver import ZoneResolver
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.storage import SQLiteRepository
from valorant_ai_coach.video import FrameSample, VideoMetadata
from valorant_ai_coach.visual.core import VisualEventEngine, project_candidate_to_v3_event
from valorant_ai_coach.visual.map_consumer import MapEventConsumer
from valorant_ai_coach.visual.map_pipeline import MapTimeline
from valorant_ai_coach.visual.models import VisualObservation
from valorant_ai_coach.visual.runtime import RealVisualAnalyzer, load_visual_profile


def test_immutable_original_validator():
    result = subprocess.run(
        [
            sys.executable,
            str(resource_path("config/map_zone_v3/tests/validate_map_zone_patch_v3.py")),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "OK (24 cases)" in result.stdout


CASES = json.loads(
    resource_path("config/map_zone_v3/tests/map_zone_runtime_cases_v3.json").read_text()
)["cases"]
ROUTES = [case for case in CASES if "sequence" in case]


def timeline(definition, route):
    label_only = definition.map_id == "three_site_fixture"
    if label_only:
        # Supplied tri_c_site overlaps tri_hub completely. Do not repair the
        # immutable fixture or guess a polygon winner. Exercise real label
        # resolution using explicit test-only records for this topology fixture.
        definition = deepcopy(definition)
        definition.callouts = {
            "location_label_policy": {"stable_duration_sec": 0.45},
            "records": {
                z: {"zone_id": z, "confidence_cap": 0.99, "aliases": {}}
                for z in definition.zone_index
            },
        }
    resolver = ZoneResolver(definition)
    result = []
    for zone_id in [*route, route[-1]]:
        point = Polygon(definition.zone_index[zone_id]["polygon_norm"]).representative_point()
        # 0.2s observations cover the real 0.6s transition debounce plus dwell.
        for _ in range(9):
            i = len(result)
            result.append(
                resolver.resolve(
                    time_sec=i * 0.2,
                    frame_index=i,
                    point=None if label_only else (point.x, point.y),
                    marker_confidence=0.99,
                    calibration={"status": "ok", "confidence": 0.99, "diagnostics": []},
                    label=zone_id if label_only else None,
                    label_confidence=0.99 if label_only else 0,
                )
            )
    return result


def visual_samples(resolutions):
    return [
        VisualObservation.from_mapping(
            {
                "time_sec": item["time_sec"],
                "frame_index": item["frame_index"],
                "hud_primary_state": "live_first_person",
                "analysis_eligibility": {"player_mechanics": True, "world_semantics": True},
                "minimap": {"track_confidence": 0.99},
                "motion": {"map_displacement_norm_per_sec": 0},
            }
        ).to_dict()
        for item in resolutions
    ]


@pytest.mark.parametrize("case", ROUTES, ids=lambda case: case["id"])
def test_real_resolver_visual_rotation_and_strict_round_package(case, tmp_path):
    registry = MapRegistry()
    definition = registry.load(case.get("fixture", "summit"), allow_fixture="fixture" in case)
    resolutions = timeline(definition, case["sequence"])
    samples = visual_samples(resolutions)
    engine = VisualEventEngine(map_definition=definition)
    candidates = engine.process(
        samples, {i: {"zone_resolution": r} for i, r in enumerate(resolutions)}
    )
    kinds = [candidate.type for candidate in candidates]
    assert ("rotation_started" in kinds) is case["expect"]
    if case["expect"]:
        assert "rotation_completed" in kinds
    assert "position_change" in kinds
    validator = SchemaValidator()
    for item in resolutions:
        validator.validate_zone_resolution(item)
        assert "events" not in item
    events = [
        event
        for i, candidate in enumerate(candidates)
        if (event := project_candidate_to_v3_event(candidate, event_id=f"map-{i}"))
    ]
    hud = []
    for i, item in enumerate(resolutions):
        values, quality = empty_hud_values(), empty_hud_quality()
        values["player_specific_hud_valid"] = True
        quality.update(hud_confidence=0.99, visual_confidence=0.99)
        hud.append(
            HudObservationV2(
                time_sec=item["time_sec"],
                frame_index=i,
                primary_state="live_first_person",
                values=values,
                quality=quality,
                is_player_world_view_trustworthy=True,
            ).to_dict()
        )
    end = resolutions[-1]["time_sec"]
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    packages = RoundPackageBuilder(contract=contract, validator=validator).build(
        match_id="map-test",
        video_metadata=VideoMetadata(
            tmp_path / "x.mp4", end + 1, 1920, 1080, 30, "h264", None, False, 0
        ),
        hud_observations=hud,
        hud_events=[],
        visual_events=events,
        visual_observations=engine.enriched_observations,
        zone_resolutions=resolutions,
        map_name=definition.map_id,
    )
    assert packages
    validator.validate_round_package(packages[0])
    last = packages[0]["state_snapshots"][-1]
    assert last["player_location"]["zone_id"] == case["sequence"][-1]
    assert "geometry_version" not in last


def test_ally_entry_observed_debounce_not_instantaneous():
    registry = MapRegistry()
    definition = registry.load("summit")
    resolutions = timeline(definition, ["summit_a_approach", "summit_a_site"])
    consumer = MapEventConsumer(definition, registry.runtime)
    events = []
    for r in resolutions:
        events += consumer.consume(r, [("ally-1", r)])
    starts = [item for item in events if item["type"] == "ally_entry_start"]
    entered = [item for item in events if item["type"] == "ally_enter_site"]
    assert len(starts) == len(entered) == 1
    assert entered[0]["start_sec"] - starts[0]["start_sec"] >= 0.35
    assert entered[0]["attributes"]["site"] == "A"


def test_unknown_map_and_failed_calibration_do_not_emit_zones():
    registry = MapRegistry()
    assert registry.select() is None
    definition = registry.load("summit")
    resolver = ZoneResolver(definition)
    r = resolver.resolve(
        time_sec=0,
        frame_index=0,
        point=(0.9, 0.42),
        marker_confidence=1,
        calibration={"status": "failed", "confidence": 1, "diagnostics": []},
    )
    assert r["zone_id"] is None and r["zone_confidence"] == 0
    engine = VisualEventEngine(map_definition=definition)
    assert not engine.process(visual_samples([r]), {0: {"zone_resolution": r}})


def test_missing_topology_edge_cannot_create_rotation():
    registry = MapRegistry()
    definition = deepcopy(registry.load("special_link_fixture", allow_fixture=True))
    definition.data["topology_edges"] = []
    resolutions = timeline(definition, ["sl_a_site", "sl_a_app", "sl_tp", "sl_b_app", "sl_b_site"])
    candidates = VisualEventEngine(map_definition=definition).process(
        visual_samples(resolutions), {i: {"zone_resolution": r} for i, r in enumerate(resolutions)}
    )
    assert not any(item.type.startswith("rotation_") for item in candidates)


def test_overlapping_fixture_polygons_remain_ambiguous():
    definition = MapRegistry().load("three_site_fixture", allow_fixture=True)
    resolver = ZoneResolver(definition)
    for i in range(12):
        result = resolver.resolve(
            time_sec=i * 0.2,
            frame_index=i,
            point=(0.5, 0.7),
            marker_confidence=1,
            calibration={"status": "ok", "confidence": 1, "diagnostics": []},
        )
        assert result["zone_id"] is None
        assert result["boundary_state"] == "ambiguous"


def test_reference_pixels_calibration_marker_resolver_visual_without_vlm(tmp_path):
    definition = MapRegistry().load("summit")
    image = cv2.imread(str(definition.reference_asset))
    x0, y0, x1, y1 = definition.data["coordinate_system"]["reference_map_mask_bbox_within_roi_px"]
    # Controlled overlay on the supplied reference exercises actual CV, not a mocked resolver.
    cv2.circle(
        image, (round(x0 + 0.9 * (x1 - x0)), round(y0 + 0.42 * (y1 - y0))), 4, (255, 0, 255), -1
    )
    path = tmp_path / "map.png"
    assert cv2.imwrite(str(path), image)
    profile = {
        "validated": True,
        "rois": {"minimap": [0, 0, 1, 1]},
        "minimap_colors_hsv": {"self": {"lower": [145, 240, 240], "upper": [155, 255, 255]}},
        "map_zone": {"client_build": definition.data["observed_client_builds"][0]},
    }
    contract = EventSourceContract.load(resource_path("config/event_source_contract_v1.json"))
    analyzer = RealVisualAnalyzer(contract, profile=profile)
    frames = [FrameSample(i * 0.2, path) for i in range(6)]
    hud = []
    for i, frame in enumerate(frames):
        values, quality = empty_hud_values(), empty_hud_quality()
        values["player_specific_hud_valid"] = True
        quality.update(hud_confidence=0.99, visual_confidence=0.99)
        hud.append(
            HudObservationV2(
                time_sec=frame.time_sec,
                frame_index=i,
                primary_state="live_first_person",
                values=values,
                quality=quality,
                is_player_world_view_trustworthy=True,
            ).to_dict()
        )
    result = analyzer.analyze(
        frames,
        hud,
        video_metadata=VideoMetadata(
            path, 2, image.shape[1], image.shape[0], 30, "h264", None, False, 0
        ),
    )
    assert analyzer.map_name == "summit"
    assert result.zone_resolutions[-1]["zone_id"] == "summit_a_site"
    assert result.zone_resolutions[-1]["zone_confidence"] <= 0.9
    assert result.observations[-1]["minimap"]["zone_id"] == "summit_a_site"
    assert result.observations[-1]["spatial"]["exposed_directions_count"] is None
    assert analyzer.semantic is None


def test_deprecated_map_profile_requires_migration(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"map_registry": {}}))
    with pytest.raises(ValueError, match="旧Map/Zone"):
        load_visual_profile(str(path))


def test_map_marker_tracks_require_unique_bidirectional_match():
    timeline = MapTimeline({"map_zone": {"manual_map_id": "summit"}})
    calibrated = CalibrationResult(
        "ok",
        0.9,
        (0, 0, 1, 1),
        timeline.definition.geometry_version,
        (),
        _matrix=(1, 0, 0, 0, 1, 0),
        _roi_size=(1, 1),
        _mask_bbox=(0, 0, 1, 1),
    )

    def step(t, xs, confidence=0.95):
        sample = VisualObservation.from_mapping(
            {
                "time_sec": t,
                "frame_index": round(t * 10),
                "hud_primary_state": "live_first_person",
                "analysis_eligibility": {"player_mechanics": True},
                "minimap": {
                    "ally_markers": [
                        {"x_norm": x, "y_norm": 0.4, "side": "ally", "confidence": confidence}
                        for x in xs
                    ],
                    "enemy_markers": [
                        {"x_norm": 0.5, "y_norm": 0.4, "side": "enemy", "confidence": 0.95}
                    ],
                },
            }
        ).to_dict()
        proof = {}
        timeline.resolve(sample, proof, {}, calibrated)
        return {track for track, _ in proof["ally_zone_resolutions"]}

    before = step(0, [0.1, 0.9])
    assert step(0.2, [0.11, 0.89]) == before
    ambiguous = step(0.4, [0.12, 0.13])
    assert ambiguous.isdisjoint(before) and len(ambiguous) == 2
    assert not step(0.6, [0.12, 0.13], confidence=0.6)
    after_gap = step(2, [0.12])
    assert after_gap.isdisjoint(ambiguous)


@pytest.mark.parametrize("round_confidence", [0.99, 0.6])
def test_zone_confidence_survives_package_storage_and_fact_enrichment(tmp_path, round_confidence):
    definition = MapRegistry().load("summit")
    resolver = ZoneResolver(definition)
    resolutions, hud = [], []
    for i in range(7):
        t = i * 0.2
        resolutions.append(
            resolver.resolve(
                time_sec=t,
                frame_index=i,
                point=(0.9, 0.42),
                marker_confidence=0.85,
                calibration={"status": "ok", "confidence": 0.99},
            )
        )
        values, quality = empty_hud_values(), empty_hud_quality()
        values["player_specific_hud_valid"] = True
        quality.update(hud_confidence=0.99, visual_confidence=round_confidence)
        hud.append(
            HudObservationV2(
                time_sec=t,
                frame_index=i,
                primary_state="live_first_person",
                values=values,
                quality=quality,
                is_player_world_view_trustworthy=True,
            ).to_dict()
        )
    end = hud[-1]["time_sec"]
    boundaries = [
        {
            "event_id": kind,
            "type": kind,
            "time_sec": t,
            "actor": "system",
            "attributes": {},
            "confidence": 0.99,
        }
        for kind, t in [("round_start", 0), ("round_end", end)]
    ]
    validator = SchemaValidator()
    builder = RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=validator,
    )
    package = builder.build(
        match_id="zone-confidence",
        video_metadata=VideoMetadata(tmp_path / "x.mp4", 2, 1920, 1080, 30, "h264", None, False, 0),
        hud_observations=hud,
        hud_events=boundaries,
        zone_resolutions=resolutions,
    )[0]
    expected = min(0.85, round_confidence)
    store = SQLiteRepository(tmp_path / "test.sqlite")
    store.create_match("zone-confidence", "x.mp4", {"duration_sec": 2}, "completed")
    store.save_round_package(package)
    restored = store.list_round_packages("zone-confidence")[0]
    enriched = FactBuilder().enrich(restored)
    validator.validate_round_package(enriched)
    zones = [f for f in enriched["deterministic_facts"] if f["key"] == "zone_id"]
    assert zones and all(f["confidence"] == pytest.approx(expected) for f in zones)
    assert len(zones) == len({f["time_sec"] for f in zones})
    assert FactBuilder().enrich(enriched) == enriched


@pytest.mark.parametrize("recover", [False, True])
def test_rotation_confidence_includes_same_zone_dwell(recover):
    definition = MapRegistry().load("special_link_fixture", allow_fixture=True)
    resolutions = timeline(definition, ["sl_a_site", "sl_a_app", "sl_tp", "sl_b_app"])
    seen = 0
    for r in resolutions:
        if r["zone_id"] == "sl_b_app":
            seen += 1
            if seen > 1 and (not recover or seen == 2):
                r["zone_confidence"] = 0.85
    candidates = VisualEventEngine(map_definition=definition).process(
        visual_samples(resolutions), {r["frame_index"]: {"zone_resolution": r} for r in resolutions}
    )
    completed = [c for c in candidates if c.type == "rotation_completed"]
    assert len(completed) == 1
    assert completed[0].confidence == 0.85
