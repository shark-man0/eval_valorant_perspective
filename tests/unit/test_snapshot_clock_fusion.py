"""Different source clocks must not relabel old HUD facts as current evidence."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_round_package_builder import event, observation

from valorant_ai_coach.events import EventSourceContract
from valorant_ai_coach.facts import FactBuilder
from valorant_ai_coach.resources import resource_path
from valorant_ai_coach.rounds import RoundPackageBuilder
from valorant_ai_coach.schema_validation import SchemaValidator
from valorant_ai_coach.video import VideoMetadata
from valorant_ai_coach.visual.models import VisualObservation


def visual(time):
    return VisualObservation.from_mapping({
        "time_sec": time, "frame_index": round(time * 60),
        "hud_primary_state": "live_first_person",
        "analysis_eligibility": {"player_mechanics": True, "world_semantics": True,
                                 "reason_codes": ["live_first_person"]},
        "spatial": {"cover_available": True, "confidence": .95},
        "quality": {"visual_confidence": .91, "occluded": False},
    }).to_dict()


def adapter():
    path = Path(__file__).resolve().parents[1] / "e2e/trace_adapter.py"
    spec = importlib.util.spec_from_file_location("clock_trace_adapter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.to_e2e_trace


def make_builder():
    return RoundPackageBuilder(
        contract=EventSourceContract.load(resource_path("config/event_source_contract_v1.json")),
        validator=SchemaValidator())


def test_non_aligned_visual_snapshot_does_not_retime_old_hud_facts():
    builder = make_builder()
    hud = [observation(1)]
    visuals = [visual(1.2)]
    snapshots = builder._merge_visual_snapshots(builder._state_snapshots(hud), visuals, hud)
    before, current = snapshots
    assert before["time_sec"] == 1 and before["hp"] == 100
    assert current["time_sec"] == 1.2 and current["hp"] is None
    assert current["round_time_remaining_sec"] is None
    assert current["spatial_context"]["cover_available"] is True
    assert current["source_confidence"] == {"spatial_context": .91}
    trace = adapter()(SimpleNamespace(
        round_packages=[{"round_window": {"start_sec": 0, "end_sec": 2},
                         "state_snapshots": snapshots}],
        observations=hud, visual_observations=visuals))
    row = trace["snapshots"][-1]
    assert row["time_sec"] == 1.2 and row["player_hp"] is None
    assert row["view_owner"] == "unknown" and "hud_confidence" not in row
    assert row["visual_confidence"] == .91


def test_current_aligned_hud_values_keep_their_original_evidence():
    builder = make_builder()
    hud = [observation(1)]
    snapshots = builder._merge_visual_snapshots(builder._state_snapshots(hud), [visual(1)], hud)
    assert len(snapshots) == 1
    assert snapshots[0]["hp"] == 100 and snapshots[0]["time_sec"] == 1


def test_orphan_snapshot_still_fails_without_explicit_current_source():
    builder = make_builder()
    hud = [observation(1)]
    snapshots = builder._state_snapshots(hud)
    snapshots[0]["time_sec"] = 1.2
    with pytest.raises(ValueError, match="matching HUD confidence"):
        adapter()(SimpleNamespace(round_packages=[{"state_snapshots": snapshots}],
                                  observations=hud))


@pytest.mark.parametrize("fault", ["stale_hp", "wrong_time", "wrong_spatial", "wrong_confidence",
                                  "ineligible", "occluded", "duplicate", "nan"])
def test_visual_snapshot_provenance_cannot_be_forged(fault):
    builder = make_builder()
    hud, visuals = [observation(1)], [visual(1.2)]
    snapshots = builder._merge_visual_snapshots(builder._state_snapshots(hud), visuals, hud)
    if fault == "stale_hp":
        snapshots[-1]["hp"] = 100
    elif fault == "wrong_time":
        visuals[0]["time_sec"] = 1.3
    elif fault == "wrong_spatial":
        snapshots[-1]["spatial_context"]["cover_available"] = False
    elif fault == "wrong_confidence":
        snapshots[-1]["source_confidence"]["spatial_context"] = .99
    elif fault == "ineligible":
        visuals[0]["analysis_eligibility"]["player_mechanics"] = False
    elif fault == "occluded":
        visuals[0]["quality"]["occluded"] = True
    elif fault == "duplicate":
        visuals *= 2
    else:
        snapshots[-1]["source_confidence"]["spatial_context"] = float("nan")
    with pytest.raises(ValueError):
        adapter()(SimpleNamespace(round_packages=[{"state_snapshots": snapshots}],
                                  observations=hud, visual_observations=visuals))


def resolution(time=1.2):
    return {"time_sec": time, "calibration_status": "ok", "resolution_scope": "exact_zone",
            "zone_confidence": .95, "zone_id": "MID"}


def test_non_aligned_map_snapshot_keeps_current_location_without_stale_hud():
    builder = make_builder()
    hud, zones = [observation(1)], [resolution()]
    snapshots = builder._merge_visual_snapshots(builder._state_snapshots(hud), [], hud, zones)
    assert snapshots[-1]["hp"] is None
    assert snapshots[-1]["player_location"]["zone_id"] == "MID"
    trace = adapter()(SimpleNamespace(round_packages=[{"state_snapshots": snapshots}],
                                     observations=hud, zone_resolutions=zones))
    row = trace["snapshots"][-1]
    assert row["time_sec"] == 1.2 and row["zone_id"] == "MID"
    assert "hud_confidence" not in row and "visual_confidence" not in row
    assert row["view_owner"] == "unknown"
    zones[0]["zone_id"] = "OTHER"
    with pytest.raises(ValueError):
        adapter()(SimpleNamespace(round_packages=[{"state_snapshots": snapshots}],
                                  observations=hud, zone_resolutions=zones))


def test_unknown_non_aligned_map_does_not_create_unobserved_snapshot():
    builder = make_builder()
    hud = [observation(1)]
    zone = {**resolution(), "calibration_status": "required", "zone_id": None}
    snapshots = builder._merge_visual_snapshots(builder._state_snapshots(hud), [], hud, [zone])
    assert len(snapshots) == 1 and snapshots[0]["time_sec"] == 1


def test_public_builder_and_trace_preserve_non_aligned_second_round_membership(tmp_path):
    builder = make_builder()
    hud = [observation(t) for t in (1, 2, 3, 4)]
    visuals = [visual(3.2)]
    metadata = VideoMetadata(path=tmp_path / "synthetic.mp4", duration_sec=5,
                             width=1920, height=1080, fps=60, video_codec="h264",
                             audio_codec=None, has_audio=False, file_size=0)
    packages = builder.build(
        match_id="synthetic-clock", video_metadata=metadata, hud_observations=hud,
        hud_events=[event("start1", 1, "round_start"), event("end1", 2, "round_end"),
                    event("start2", 3, "round_start"), event("end2", 4, "round_end")],
        visual_observations=visuals)
    assert len(packages) == 2
    validator = SchemaValidator()
    for package in packages:
        validator.validate_round_package(package)
    assert all(s["time_sec"] != 3.2 for s in packages[0]["state_snapshots"])
    row = next(s for s in packages[1]["state_snapshots"] if s["time_sec"] == 3.2)
    assert row["hp"] is None and row["spatial_context"]["cover_available"] is True
    trace = adapter()(SimpleNamespace(round_packages=packages, observations=hud,
                                     visual_observations=visuals))
    row = next(s for s in trace["snapshots"] if s["time_sec"] == 3.2)
    assert row["round_id"] == "sample_round_2" and row["view_owner"] == "unknown"
    facts = FactBuilder().build(packages[1])
    current = [fact for fact in facts if fact.time_sec == 3.2]
    cover = next(fact for fact in current if fact.key == "cover_available")
    assert cover.value is True and cover.confidence == .91 and cover.source == "visual"
    assert all(fact.key not in {"round_time_remaining_sec", "numbers_state", "weapon"}
               for fact in current)
