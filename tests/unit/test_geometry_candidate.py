import json

import cv2
import numpy as np
import pytest
from test_geometry_edge_experiment import changing_brightness

from scripts.diagnostics.build_geometry_candidate import build, content_mask, sampling_plan
from scripts.diagnostics.diagnose_geometry_edges import raw_scores
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
    raw = json.loads((tmp_path / "hud_layout.templates.json").read_text(encoding="utf-8"))
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
    raw = json.loads((tmp_path / "hud_layout.templates.json").read_text(encoding="utf-8"))
    assert raw["anchors"] == {} and not list(tmp_path.glob("*.png"))


@pytest.mark.parametrize("threshold", [.89, True, float("nan"), 1.01])
def test_invalid_threshold_is_not_silently_relaxed(tmp_path, threshold):
    with pytest.raises(ValueError, match="NCC threshold"):
        build(changing_brightness(), layout(), {
            "anchors": {"round_timer": {"threshold": threshold}}}, tmp_path)


def policy():
    return {"interior_exclusion_norm": [.08, .08, .92, .92], "reader_padding_px": 4,
            "region_exclusions": {}}


def test_content_mask_excludes_center_and_configured_numeric_fields():
    original = np.full((100, 160), 255, np.uint8)
    base = {"readers": {"player_hp_armor": {"fields": {"hp": [0, 0, .2, .2]}}}}
    result = content_mask(original, "player_hp_armor", layout(), base, policy(), 160, 100)
    assert not result[8:92, 12:148].any()
    assert not result[:24, :36].any()
    assert result[-1, -1] == 255 and original.min() == 255


def test_dynamic_subregion_is_projected_from_layout_not_sample_coordinates():
    source_layout = HudLayout("1.0", True, (160, 100), {
        "top_match_bar": NormalizedRoi(0, 0, 1, 1),
        "changing_score": NormalizedRoi(.75, 0, .25, .25)})
    config = {**policy(), "region_exclusions": {"top_match_bar": ["changing_score"]}}
    result = content_mask(np.full((100, 160), 255, np.uint8), "top_match_bar", source_layout,
                          {}, config, 160, 100)
    assert not result[:29, 116:].any()
    assert result[-1, -1] == 255


def test_new_temporal_split_excludes_all_old_training_and_validation_frames():
    old = sampling_plan(720, [])
    new = sampling_plan(720, old["training"] + old["validation"], temporal_split=True)
    assert max(new["training"]) < 355 and min(new["validation"]) > 365
    assert min(abs(a - b) for a in new["training"] for b in new["validation"]) >= 10


@pytest.mark.parametrize("rectangle", [[0, 0, 1, float("nan")], [.9, 0, .1, 1], [0, 0, 2, 1]])
def test_bad_content_rectangle_fails_closed(rectangle):
    with pytest.raises(ValueError):
        content_mask(np.full((100, 160), 255, np.uint8), "abilities", layout(), {},
                     {**policy(), "interior_exclusion_norm": rectangle}, 160, 100)


def test_numeric_content_changes_cannot_raise_or_lower_masked_ncc():
    gray = np.full((100, 160), 20, np.uint8)
    cv2.rectangle(gray, (3, 3), (156, 96), 220, 2)
    mask = content_mask(np.full_like(gray, 255), "abilities", layout(), {}, policy(), 160, 100)
    changed = gray.copy()
    rng = np.random.default_rng(42)
    changed[mask == 0] = rng.integers(0, 255, np.count_nonzero(mask == 0), dtype=np.uint8)
    original_score = raw_scores([cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)], gray, mask)[0]
    changed_score = raw_scores([cv2.cvtColor(changed, cv2.COLOR_GRAY2BGR)], gray, mask)[0]
    assert original_score >= .90
    assert changed_score == pytest.approx(original_score, abs=1e-6)


def test_reused_training_does_not_reuse_examined_validation():
    earlier = sampling_plan(720, [], temporal_split=True)
    history = earlier["training"] + earlier["validation"]
    current = sampling_plan(720, history, temporal_split=True, phase=5.75,
                            training_override=earlier["training"])
    assert current["training"] == earlier["training"] and current["training_reused"] is True
    assert all(abs(time - old) >= 2 for time in current["validation"] for old in history)
    with pytest.raises(ValueError, match="training partition"):
        sampling_plan(720, [], temporal_split=True,
                      training_override=earlier["validation"])
