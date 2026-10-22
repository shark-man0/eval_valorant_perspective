from __future__ import annotations

import copy
import json

import pytest

from valorant_ai_coach.visual.development_path_viewer import write_candidate_path_html
from valorant_ai_coach.visual.development_trajectory import analyze_candidate_path


def observation(i, *, point=None, zone="A"):
    return {
        "qualification": "development_only", "ownership": {"identity": "UNKNOWN",
                                                           "view_eligible": True},
        "formal_self_position_fact": None, "source_id": "synthetic",
        "acquisition_id": "single-window", "context_sha256": "profile-geometry-roi",
        "map_id": "example", "geometry_version": "synthetic-v1",
        "time_sec": i*.2, "frame_index": i, "map_segment": 0,
        "map_position_norm": [.5, .5] if point is None else point,
        "calibration": {"status": "ok"}, "appearance": {"reason": "appearance_only"},
        "zone_resolution": {"zone_id": zone, "boundary_state": "clear",
                            "held_from_previous": False, "ownership": "UNKNOWN",
                            "qualification": "development_only"},
    }


def analyze(records, **kwargs):
    return analyze_candidate_path(records, reference_size_px=(800, 1000), **kwargs)


def test_observed_spans_and_quiet_windows_are_not_formal_facts():
    records = [observation(i) for i in range(8)]
    original = copy.deepcopy(records)
    result = analyze(records)
    assert records == original
    assert result["ownership"] == "UNKNOWN"
    assert result["formal_self_position_fact"] is None
    assert len(result["segments"]) == 1
    assert result["segments"][0]["observed_span_sec"] == pytest.approx(1.4)
    assert result["zone_observation_spans_sec"] == {"A": pytest.approx(1.4)}
    assert result["motion_observation_spans_sec"]["low_displacement_candidate"] == pytest.approx(.6)
    assert all("type" not in edge and "actor" not in edge for edge in result["edges"])


def test_moving_window_uses_reference_pixels_and_no_world_speed():
    result = analyze([observation(i, point=[.1+i*.01, .5]) for i in range(8)])
    edge = result["edges"][-1]
    assert edge["motion"] == "moving_candidate"
    assert edge["chord_reference_px"] == pytest.approx(8)
    assert edge["ending_window_displacement_reference_px"] == pytest.approx(40)


@pytest.mark.parametrize("field,value", [
    ("source_id", "other"), ("acquisition_id", "other"), ("context_sha256", "changed"),
    ("geometry_version", "v2"), ("map_id", "other"), ("map_segment", 1),
    ("time_sec", .6), ("time_sec", 0), ("frame_index", 0),
    ("map_position_norm", [.9, .9]),
])
def test_discontinuities_start_fresh_without_edge_or_transition(field, value):
    a, b = observation(0), observation(1, zone="B")
    b[field] = value
    result = analyze([a, b])
    assert len(result["segments"]) == 2
    assert result["edges"] == []
    assert result["zone_change_brackets"] == []


@pytest.mark.parametrize("kind", ["missing", "view", "calibration", "outside", "nan"])
def test_unknown_observation_breaks_path_and_zone_memory(kind):
    records = [observation(i, zone="A" if i < 2 else "B") for i in range(3)]
    mid = records[1]
    if kind == "missing":
        mid["map_position_norm"] = None
    elif kind == "view":
        mid["ownership"]["view_eligible"] = False
    elif kind == "calibration":
        mid["calibration"]["status"] = "calibration_required"
    else:
        mid["map_position_norm"] = [1.1 if kind == "outside" else float("nan"), .5]
    result = analyze(records)
    assert result["position_unknown_observations"] == 1
    assert result["edges"] == []
    assert result["zone_change_brackets"] == []


def test_unknown_zone_has_no_dwell_but_bounds_change_on_contiguous_measured_path():
    records = [observation(0), observation(1, zone=None), observation(2, zone="B")]
    result = analyze(records)
    assert result["zone_observation_spans_sec"] == {}
    assert len(result["edges"]) == 2
    assert result["zone_change_brackets"] == [{
        "candidate_kind": "zone_change_bracket", "from_zone_id": "A", "to_zone_id": "B",
        "from_index": 0, "to_index": 2, "segment": 0, "crossing_time": "UNKNOWN",
        "qualification": "development_only", "ownership": "UNKNOWN",
    }]


@pytest.mark.parametrize("field,value", [("held_from_previous", True),
                                         ("boundary_state", "boundary"),
                                         ("qualification", None), ("ownership", None)])
def test_held_or_untagged_zone_never_contributes_dwell(field, value):
    records = [observation(0), observation(1)]
    records[1]["zone_resolution"][field] = value
    assert analyze(records)["zone_observation_spans_sec"] == {}


@pytest.mark.parametrize("field,value", [("qualification", "production"),
                                         ("source_id", ""), ("time_sec", float("inf")),
                                         ("formal_self_position_fact", {"x": .5})])
def test_contract_rejects_unscoped_or_promoted_records(field, value):
    record = observation(0)
    record[field] = value
    with pytest.raises(ValueError):
        analyze([record])


def test_viewer_escapes_metadata_and_preserves_unknown_slots(tmp_path):
    records = [observation(0), observation(1)]
    records[1]["map_position_norm"] = None
    records[0]["appearance"]["reason"] = "</script><script>alert('x')</script>"
    report = analyze(records)
    target = tmp_path/"path_PRIVATE.html"
    write_candidate_path_html(target, report, reference_png=b"synthetic",
                              reference_bbox=(0, 0, 800, 1000), zones=[])
    text = target.read_text(encoding="utf-8")
    payload = text.split('<script id="data" type="application/json">')[1].split("</script>")[0]
    assert "</script>" not in payload
    decoded = json.loads(payload)
    assert decoded["report"]["samples"][1]["point_norm"] is None
    assert decoded["frames"] == [None, None]
    assert "fetch(" not in text and "http://" not in text
    with pytest.raises(ValueError, match="frame slot"):
        write_candidate_path_html(target, report, reference_png=b"synthetic",
                                  reference_bbox=(0, 0, 800, 1000), zones=[],
                                  source_frames_jpeg=[b"one frame"])
