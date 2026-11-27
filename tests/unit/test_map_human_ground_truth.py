from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _module():
    path = (Path(__file__).resolve().parents[2]
            / "scripts/map_canonical/score_human_ground_truth.py")
    spec = importlib.util.spec_from_file_location("score_human_ground_truth", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _frame(i, group, sec, roi=None, zone=None, status=None, window=None):
    prediction = None if roi is None else {"roi_px": roi, "zone_id": zone,
                                           "zone_status": status}
    return {"id": i, "group": group, "sec": sec, "sample_sha256": f"s{i}", "window": window,
            "metres_per_roi_px": 0.5, "prediction": prediction}


def _row(i, role, click=None, site=None):
    return {"index": i, "sample_ref": f"s{i}", "role": role, "center_roi_px": click,
            "site_label": site}


def test_positions_misses_and_sites_are_scored_against_the_human_click() -> None:
    m = _module()
    key = {"frames": [
        _frame(0, "eligible", 1, [10, 10], "haven_b_plant", "inside"),
        _frame(1, "eligible", 2, [10, 10]),
        _frame(2, "eligible", 3, [10, 10]),
        _frame(5, "eligible", 6, [10, 10]),
        _frame(3, "no_position", 4),
        _frame(4, "no_position", 5),
    ], "windows": []}
    labels = {"rows": [_row(0, "SELF", [12, 10], "B"), _row(1, "SELF", [30, 10], "OUTSIDE"),
                       _row(2, "UNKNOWN"), _row(3, "SELF", [5, 5]), _row(4, "NOT_VISIBLE"),
                       _row(5, "SELF", [10, 10])]}
    result = m.score(labels, key)
    eligible = result["positions"]["eligible"]
    assert (eligible["decided"], eligible["same_place"]) == (3, 2)  # 1 m, 10 m, exact
    assert result["positions"]["no_position"]["missed_self_visible"] == 1
    assert result["zone_vs_human_site"]["plant_zone_same_site"] == 1


def test_windows_use_only_human_clicks() -> None:
    m = _module()
    frames = [_frame(i, "change", 10 + i, [0, 0], window="W0") for i in range(3)]
    frames += [_frame(3 + i, "plant_arrival", 20 + i, [0, 0], window="W1") for i in range(2)]
    key = {"frames": frames, "windows": [
        {"window": "W0", "group": "change",
         "claim": {"start_sec": 10, "end_sec": 12, "displacement_m": 8.0}},
        {"window": "W1", "group": "plant_arrival",
         "claim": {"before_sec": 20, "after_sec": 21}}]}
    labels = {"rows": [_row(0, "SELF", [0, 0]), _row(1, "SELF", [4, 0]),
                       _row(2, "SELF", [6, 0]), _row(3, "SELF", [0, 0], "OUTSIDE"),
                       _row(4, "SELF", [9, 0], "A")]}
    result = m.score(labels, key)
    change, arrival = result["windows"]
    assert (change["human_m"], change["confirmed"]) == (3.0, False)
    assert arrival["entry_from_outside_site"] is True


def test_labels_from_another_package_are_refused() -> None:
    m = _module()
    key = {"frames": [_frame(0, "eligible", 1, [1, 1])], "windows": []}
    with pytest.raises(ValueError):
        m.score({"rows": [{"index": 0, "sample_ref": "other", "role": "SELF"}]}, key)
