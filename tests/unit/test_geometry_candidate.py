import json

import numpy as np
import pytest
from test_geometry_edge_experiment import changing_brightness

from scripts.diagnostics.build_geometry_candidate import build, sampling_plan
from valorant_ai_coach.hud.calibrate_temporal import ANCHORS
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.templates import HudTemplateProfile


def test_plan_excludes_previously_examined_frames_and_separates_roles():
    plan = sampling_plan(720, [3.25, 13.25, 201.5])
    assert len(plan["training"]) >= 8 and len(plan["validation"]) >= 8
    assert not set(plan["training"]) & set(plan["validation"])
    assert all(0 <= time < 720 for role in ("training", "validation") for time in plan[role])
    assert all(abs(time - old) >= 2 for role in ("training", "validation")
               for time in plan[role] for old in plan["previous_geometry_pts"])


@pytest.mark.parametrize("end,previous", [(10, []), (float("nan"), []),
                                        (720, [float("inf")]), (720, [-1])])
def test_invalid_or_insufficient_sampling_rejected(end, previous):
    with pytest.raises(ValueError):
        sampling_plan(end, previous)


def layout():
    return HudLayout("1.0", True, (160, 100), {
        name: NormalizedRoi(0, 0, 1, 1) for name in ANCHORS})


def test_candidate_contains_only_geometry_assets_and_keeps_threshold(tmp_path):
    training = changing_brightness()
    before = [frame.copy() for frame in training]
    report = build(training, layout(), {"anchors": {}, "signals": {"identity": "must_not_copy"}},
                   tmp_path)
    raw = json.loads((tmp_path / "hud_layout.templates.json").read_text())
    assert set(raw["anchors"]) == set(ANCHORS)
    assert raw["signals"] == {} and raw["readers"] == {}
    assert all(spec["threshold"] == .90 and "mask" in spec for spec in raw["anchors"].values())
    assert all(row["training_accept_count"] == 32 for row in report.values())
    profile = HudTemplateProfile.load(tmp_path / "hud_layout.templates.json")
    assert profile.raw["signals"] == {}
    assert all(np.array_equal(a, b) for a, b in zip(before, training, strict=True))


def test_no_candidate_is_fabricated_from_flat_frames(tmp_path):
    report = build([np.full((100, 160, 3), 70, np.uint8)] * 16, layout(), {}, tmp_path)
    assert all(row["status"] == "training_structure_insufficient" for row in report.values())
    raw = json.loads((tmp_path / "hud_layout.templates.json").read_text())
    assert raw["anchors"] == {} and not list(tmp_path.glob("*.png"))


@pytest.mark.parametrize("threshold", [.89, True, float("nan"), 1.01])
def test_invalid_threshold_is_not_silently_relaxed(tmp_path, threshold):
    with pytest.raises(ValueError, match="NCC threshold"):
        build(changing_brightness(), layout(), {
            "anchors": {"round_timer": {"threshold": threshold}}}, tmp_path)
