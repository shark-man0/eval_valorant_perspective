from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from valorant_ai_coach.facts.map_position_promotion import (
    MapGeometry,
    PromotionSettings,
    position_candidates,
)

GEO = MapGeometry("map-a", "test_map", 10.0)  # 10 reference px per metre
CAL = {
    "corroborated": 0.86,
    "temporally_supported:self_ring": 0.80,
    "temporally_supported:map_library_rim": 0.69,
    "isolated:self_ring": 0.55,
    "isolated:map_library_rim": 0.86,
}


def _point(sec: int, xy: tuple[float, float], methods: list[str], zone: str | None = None):
    return {
        "kind": "selected", "map_id": "map-a", "map_reference_px": list(xy),
        "methods_agreeing": methods, "selection_method": methods[0],
        "zone_candidate": zone, "sample": {"sample_sha256": f"s{sec}"},
        "canonical_pixel_verification": "native_frame_pixels",
    }


def _report(points: dict[int, dict]) -> dict:
    return {
        "schema": "development_recorder_map_path_v1", "qualified": False,
        "formal_outputs": 0, "canonical_pass": {}, "timeline_sha256": "t",
        "second_rows": [
            {"timestamp": sec, "recorder_map_observations": [p]} for sec, p in points.items()
        ],
    }


def _timeline(seconds: range, ended: set[int] = frozenset()) -> dict:
    return {"seconds": [
        {"timestamp": s, "round_state": {"value": "ENDED" if s in ended else "ACTIVE"}}
        for s in seconds
    ]}


BOTH = ["self_ring", "map_library_rim"]


def test_isolated_reading_is_never_eligible_even_with_high_confidence() -> None:
    report = _report({10: _point(10, (0, 0), ["map_library_rim"])})
    result = position_candidates(report, _timeline(range(0, 30)), [(1, 0, 29)], GEO,
                                 calibration=CAL)
    (position,) = result["positions"]
    assert position["support"] == "isolated"
    assert position["confidence"] == 0.86
    assert position["eligible"] is False


def test_temporal_support_needs_a_reachable_neighbour_in_the_same_round() -> None:
    points = {
        10: _point(10, (0, 0), ["self_ring"]),
        11: _point(11, (50, 0), ["self_ring"]),   # 5 m: reachable
        20: _point(20, (0, 0), ["self_ring"]),
        21: _point(21, (200, 0), ["self_ring"]),  # 20 m in one second: impossible
        30: _point(30, (0, 0), ["self_ring"]),    # neighbour 31 is in another round
        31: _point(31, (10, 0), ["self_ring"]),
    }
    rounds = [(1, 0, 30), (2, 31, 40)]
    result = position_candidates(_report(points), _timeline(range(0, 41)), rounds, GEO,
                                 calibration=CAL)
    support = {p["sec"]: p["support"] for p in result["positions"]}
    assert support[10] == support[11] == "temporally_supported"
    assert support[20] == support[21] == "isolated"
    assert support[30] == support[31] == "isolated"


def test_uncalibrated_or_low_confidence_support_is_not_eligible() -> None:
    points = {10: _point(10, (0, 0), BOTH), 11: _point(11, (5, 0), ["map_library_rim"])}
    calibration = {"corroborated": 0.86, "temporally_supported:map_library_rim": 0.5}
    result = position_candidates(_report(points), _timeline(range(0, 20)), [(1, 0, 19)],
                                 GEO, calibration=calibration)
    eligible = {p["sec"]: p["eligible"] for p in result["positions"]}
    assert eligible == {10: True, 11: False}
    result = position_candidates(_report(points), _timeline(range(0, 20)), [(1, 0, 19)],
                                 GEO, calibration={})
    assert not any(p["eligible"] for p in result["positions"])


def test_seconds_outside_confirmed_or_playable_rounds_are_dropped() -> None:
    points = {s: _point(s, (0, 0), BOTH) for s in (5, 15, 16)}
    result = position_candidates(_report(points), _timeline(range(0, 20), ended={16}),
                                 [(1, 10, 19)], GEO, calibration=CAL)
    assert [p["sec"] for p in result["positions"]] == [15]


def test_hold_change_and_site_entry_without_path_or_speed() -> None:
    points = {s: _point(s, (0, 0), BOTH, "A Main") for s in range(10, 15)}
    points.update({
        15: _point(15, (60, 0), BOTH, "A Main"),
        16: _point(16, (120, 0), BOTH, "A Site (plant)"),
    })
    result = position_candidates(_report(points), _timeline(range(0, 20)), [(1, 0, 19)],
                                 GEO, calibration=CAL, aliases={"A Site (plant)": "A Plant"})
    events = {e["type"]: e for e in result["events"]}
    hold = events["position_hold"]
    assert (hold["start_sec"], hold["end_sec"]) == (10, 14)
    assert hold["zone_id"] == "test_map_a_main"
    change = events["position_change"]
    assert (change["start_sec"], change["end_sec"]) == (14, 16)
    assert change["displacement_m"] == 12.0
    assert change["to_zone_id"] == "test_map_a_plant"
    assert events["site_entry"]["zone_id"] == "test_map_a_plant"
    assert result["continuous_path_inferred"] is False
    assert result["instantaneous_speed_inferred"] is False
    forbidden = {"path", "trajectory", "speed", "velocity", "speed_mps", "interpolated"}
    for event in result["events"]:
        assert not forbidden & set(event)
    assert result["formal_outputs"] == 0
    assert result["qualification"] == "development_candidate"


def test_gap_longer_than_allowed_splits_holds() -> None:
    points = {s: _point(s, (0, 0), BOTH) for s in (10, 11, 12, 16, 17, 18)}
    result = position_candidates(_report(points), _timeline(range(0, 20)), [(1, 0, 19)],
                                 GEO, calibration=CAL,
                                 settings=PromotionSettings(min_hold_seconds=2))
    holds = [(e["start_sec"], e["end_sec"]) for e in result["events"]
             if e["type"] == "position_hold"]
    assert holds == [(10, 12), (16, 18)]


def test_unbound_report_is_refused() -> None:
    report = _report({})
    report["formal_outputs"] = 1
    with pytest.raises(ValueError):
        position_candidates(report, _timeline(range(0, 5)), [], GEO, calibration=CAL)


def _calibrate_module():
    path = Path(__file__).resolve().parents[2] / "scripts/map_canonical/calibrate_positions.py"
    spec = importlib.util.spec_from_file_location("calibrate_positions", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_calibration_counts_unclear_as_wrong_and_requires_full_labels() -> None:
    module = _calibrate_module()
    sample = [{"id": i, "tier": "corroborated" if i < 4 else "isolated:self_ring"}
              for i in range(8)]
    result = module.calibrate(sample, {"correct": [0, 1, 2, 3, 4, 5], "wrong": [6],
                                       "unclear": [7]})
    assert result["tiers"]["isolated:self_ring"]["precision_excluding_unclear"] == 0.6667
    assert result["confidence"]["isolated:self_ring"] == round(module.wilson_lower(2, 4), 4)
    assert result["confidence"]["corroborated"] == round(module.wilson_lower(4, 4), 4)
    with pytest.raises(ValueError):
        module.calibrate(sample, {"correct": [0, 1]})
