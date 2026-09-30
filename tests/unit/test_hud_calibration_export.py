from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.calibrate import create_anchor_profile
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.resources import resource_path


def test_reference_export_reloads_and_measures_actual_anchor_geometry(tmp_path: Path) -> None:
    layout_path = resource_path("config/hud_layout_1080p_v3.json")
    reference = tmp_path / "reference.png"
    image = np.random.default_rng(1).integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
    assert cv2.imwrite(str(reference), image)
    output = tmp_path / "profile"
    exported_layout = create_anchor_profile(layout_path, reference, output)
    assert exported_layout.read_bytes() == layout_path.read_bytes()
    profile = HudTemplateProfile.load(output / "hud_layout.templates.json")
    layout = HudLayout.load(exported_layout)
    boxes, scores, diagnostics = profile.detect_anchors(image, layout)
    assert len(boxes) == 4 and min(scores.values()) > 0.99
    assert not diagnostics
    assert layout.validate_calibration(
        1920,
        1080,
        detected_anchors=boxes,
        letterboxed=False,
        crop_applied=False,
    ).calibrated
    with pytest.raises(FileExistsError):
        create_anchor_profile(layout_path, reference, output)


def test_reference_export_rejects_wrong_resolution_without_publishing(tmp_path: Path) -> None:
    reference = tmp_path / "resized.png"
    assert cv2.imwrite(str(reference), np.zeros((720, 1280, 3), dtype=np.uint8))
    with pytest.raises(ValueError, match="基準解像度"):
        create_anchor_profile(
            resource_path("config/hud_layout_1080p_v3.json"), reference, tmp_path / "profile"
        )
    assert not (tmp_path / "profile").exists()


def test_mask_excludes_dynamic_pixels_and_keeps_geometry_checks(tmp_path):
    layout_path = resource_path("config/hud_layout_1080p_v3.json")
    layout = HudLayout.load(layout_path)
    image = np.random.default_rng(4).integers(0, 256, (1080, 1920, 3), dtype=np.uint8)
    reference = tmp_path / "reference.png"
    assert cv2.imwrite(str(reference), image)
    names = ("round_timer", "top_match_bar", "player_hp_armor", "abilities")
    # A disjoint small patch in each ROI models a stable UI outline.
    regions = {name: [[.05, .1, .18, .35]] for name in names}
    exported = create_anchor_profile(layout_path, reference, tmp_path / "profile",
                                     anchor_regions=regions)
    profile = HudTemplateProfile.load(exported.with_suffix(".templates.json"))
    changed = np.random.default_rng(9).integers(0, 256, image.shape, dtype=np.uint8)
    for name in names:
        x1, y1, x2, y2 = layout.normalized_roi(name).pixel_bounds(1920, 1080)
        mask = cv2.imread(str(tmp_path / "profile" / "anchors" / f"{name}.mask.png"), 0)
        changed[y1:y2, x1:x2][mask > 0] = image[y1:y2, x1:x2][mask > 0]
    boxes, scores, diagnostics = profile.detect_anchors(changed, layout)
    assert len(boxes) == 4 and min(scores.values()) > .99, diagnostics
    assert layout.validate_calibration(1920, 1080, detected_anchors=boxes,
                                       letterboxed=False, crop_applied=False).calibrated
    analysis = RealHudAnalyzer(exported).observe_frames([changed])
    assert analysis.calibration.calibrated
    assert analysis.observations[0]["values"]["player_specific_hud_valid"] is False
    stats = analysis.calibration_diagnostics
    assert stats["counts"]["frames"] == 1
    assert stats["counts"]["geometry_valid_state_unknown"] == 1
    assert stats["fresh_geometry_success_rate"] == 1.0
    assert all(anchor["accepted_count"] == 1 for anchor in stats["anchors"])
    shifted = cv2.warpAffine(changed, np.float32([[1, 0, 80], [0, 1, 0]]), (1920, 1080))
    shifted_boxes, _, _ = profile.detect_anchors(shifted, layout)
    assert not layout.validate_calibration(1920, 1080, detected_anchors=shifted_boxes,
                                           letterboxed=False, crop_applied=False).calibrated
    # A blank scene or missing mask must never silently use an unmasked template.
    assert not profile.detect_anchors(np.zeros_like(image), layout)[0]
    before = profile.fingerprint(exported)
    mask_path = tmp_path / "profile" / "anchors" / "round_timer.mask.png"
    assert cv2.imwrite(str(mask_path), np.zeros((2, 2), dtype=np.uint8))
    assert before != profile.fingerprint(exported)
    boxes, _, diagnostics = profile.detect_anchors(changed, layout)
    assert "round_timer" not in boxes
    assert any("mask must match" in message for message in diagnostics)
