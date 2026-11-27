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


def _timeline(seconds: range, ended: set[int] = frozenset(),
              views: dict[int, tuple[str, str]] | None = None) -> dict:
    views = views or {}

    def state(value: str) -> dict:
        return {"value": value, "status": "OBSERVED"}

    return {"seconds": [
        {"timestamp": s, "round_state": {"value": "ENDED" if s in ended else "ACTIVE"},
         "camera_state": state(views.get(s, ("SELF", "ALIVE"))[0]),
         "life_state": state(views.get(s, ("SELF", "ALIVE"))[1])}
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


@pytest.mark.parametrize("view", [("SPECTATING", "DEAD"), ("SELF", "DEAD"),
                                  ("REPLAY", "ALIVE")])
def test_death_spectating_or_replay_inside_the_gap_splits_runs(view: tuple[str, str]) -> None:
    points = {s: _point(s, (0, 0), BOTH) for s in (10, 11, 12, 15, 16, 17)}
    settings = PromotionSettings(min_hold_seconds=2, max_gap_seconds=3)
    joined = position_candidates(_report(points), _timeline(range(0, 20)), [(1, 0, 19)],
                                 GEO, calibration=CAL, settings=settings)
    assert [(e["start_sec"], e["end_sec"]) for e in joined["events"]] == [(10, 17)]
    split = position_candidates(_report(points), _timeline(range(0, 20), views={14: view}),
                                [(1, 0, 19)], GEO, calibration=CAL, settings=settings)
    assert [(e["start_sec"], e["end_sec"]) for e in split["events"]] == [(10, 12), (15, 17)]
    assert split["counts"]["runs_split_by_view_change"] == 1


def test_change_does_not_join_positions_across_a_revive() -> None:
    points = {10: _point(10, (0, 0), BOTH), 12: _point(12, (100, 0), BOTH)}
    result = position_candidates(
        _report(points), _timeline(range(0, 20), views={11: ("SELF", "DEAD")}),
        [(1, 0, 19)], GEO, calibration=CAL)
    assert not [e for e in result["events"] if e["type"] == "position_change"]


def test_arrival_in_a_plant_zone_from_an_unknown_zone_is_not_a_site_entry() -> None:
    points = {10: _point(10, (0, 0), BOTH), 11: _point(11, (20, 0), BOTH, "A Site (plant)"),
              20: _point(20, (0, 0), BOTH, "A Main"),
              21: _point(21, (20, 0), BOTH, "A Site (plant)")}
    result = position_candidates(_report(points), _timeline(range(0, 30)), [(1, 0, 29)],
                                 GEO, calibration=CAL)
    entries = [e for e in result["events"] if e["type"] == "site_entry"]
    assert [(e["before_sec"], e["from_zone_id"]) for e in entries] == [(20, "test_map_a_main")]
    assert result["diagnostics"]["site_arrival_unconfirmed"] == {"from_report_unknown": 1}


def test_zone_needs_the_metric_margin_from_every_boundary() -> None:
    square = [[0, 0], [100, 0], [100, 100], [0, 100]]
    zones = {"ref": {"A Main": square, "A Site (plant)": [[100, 0], [200, 0], [200, 100],
                                                          [100, 100]]}}
    points = {s: _point(s, xy, BOTH) for s, xy in
              ((10, (50, 50)), (11, (95, 50)), (12, (150, 50)), (13, (300, 50)))}
    for point in points.values():
        point["reference_sha256"] = "ref"
    result = position_candidates(_report(points), _timeline(range(0, 20)), [(1, 0, 19)],
                                 GEO, calibration=CAL, zones=zones,
                                 settings=PromotionSettings(coordinate_error_m=1.25))
    status = {p["sec"]: (p["zone_status"], p["zone_id"]) for p in result["positions"]}
    assert status == {10: ("inside", "test_map_a_main"), 11: ("boundary", None),
                      12: ("inside", "test_map_a_site_plant"),
                      13: ("outside_registered", None)}
    # 10 -> 11 -> 12 crosses the boundary; the reading before the boundary decides.
    entries = [e for e in result["events"] if e["type"] == "site_entry"]
    assert [(e["before_sec"], e["after_sec"], e["from_zone_id"]) for e in entries] == [
        (10, 12, "test_map_a_main")]
    # From outside every registered Zone, through the boundary: not an entry.
    points = {s: _point(s, xy, BOTH) for s, xy in
              ((10, (50, 150)), (11, (150, 105)), (12, (150, 50)))}
    for point in points.values():
        point["reference_sha256"] = "ref"
    result = position_candidates(_report(points), _timeline(range(0, 20)), [(1, 0, 19)],
                                 GEO, calibration=CAL, zones=zones)
    assert not [e for e in result["events"] if e["type"] == "site_entry"]
    assert result["diagnostics"]["site_arrival_unconfirmed"] == {
        "from_outside_registered": 1}


def test_change_within_the_coordinate_error_of_the_threshold_is_dropped() -> None:
    points = {10: _point(10, (0, 0), BOTH), 11: _point(11, (55, 0), BOTH),
              20: _point(20, (0, 0), BOTH), 21: _point(21, (70, 0), BOTH)}
    result = position_candidates(_report(points), _timeline(range(0, 30)), [(1, 0, 29)],
                                 GEO, calibration=CAL)
    changes = [e for e in result["events"] if e["type"] == "position_change"]
    assert [(e["start_sec"], e["displacement_m"]) for e in changes] == [(20, 7.0)]
    assert result["diagnostics"]["position_change_within_coordinate_error"] == 1


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
