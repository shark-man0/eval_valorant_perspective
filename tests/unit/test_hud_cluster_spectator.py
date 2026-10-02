import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.calibrate_profile import structure_reference
from valorant_ai_coach.hud.identity import live_identity
from valorant_ai_coach.hud.spectator import detect_panel, generate_panel_reference, panel_components


def test_mixed_modes_accept_supported_minority_without_relaxing_ncc():
    shape = np.full((120, 130), 50, np.uint8)
    cv2.rectangle(shape, (4, 4), (115, 115), 220, 2)
    cv2.line(shape, (15, 30), (90, 90), 150, 3)
    crops = [shape.copy() if i % 4 < 2 else np.full_like(shape, 65) for i in range(32)]
    stats = {}
    result = structure_reference(crops, stats)
    assert result is not None
    assert stats["training_accept_count"] == 8
    assert stats["holdout_accept_count"] == 8
    assert stats["holdout_median"] >= 0.90


def test_training_only_mode_rejected_with_specific_diagnostics():
    shape = np.full((120, 130), 50, np.uint8)
    cv2.rectangle(shape, (4, 4), (115, 115), 220, 2)
    stats = {}
    assert (
        structure_reference(
            [shape if i % 2 == 0 else np.zeros_like(shape) for i in range(32)], stats
        )
        is None
    )
    assert stats["holdout_rejected"] == 1
    assert stats["holdout_accept_count"] == 0


def test_panel_structure_not_background_matching(panel_images):
    positive, negative = panel_images(160, 126)
    frames = [panel_images(160, 126, i)[0 if i % 4 >= 2 else 1] for i in range(32)]
    stats = {}
    labels = generate_panel_reference(frames, stats)
    assert labels is not None and stats["holdout_accept_count"] == 8
    assert detect_panel(positive, labels)["panel_present"] is True
    for offset in (0, 30, 60):
        _, changing_scene = panel_images(160, 126, offset)
        result = detect_panel(changing_scene, labels)
        assert result["checked"] is True and result["panel_present"] is False
    assert detect_panel(negative, None)["checked"] is False
    assert detect_panel(np.zeros_like(negative), labels)["checked"] is False
    assert detect_panel(negative[::2], labels)["checked"] is False
    # Partial occlusion: absence cannot be concluded from a missed full-panel match.
    partial = negative.copy()
    partial[:20] = positive[:20]
    result = detect_panel(partial, labels)
    assert result["checked"] is False and result["panel_present"] is None


def test_no_positive_panel_structure_no_negative_evidence(panel_images):
    _, scene = panel_images(160, 126)
    stats = {}
    assert generate_panel_reference([scene] * 32, stats) is None
    assert stats["structural_rejected"] == 16
    assert panel_components(np.zeros((100, 100), np.uint8)) is None


def test_absent_flag_without_executed_detector_is_not_evidence(live_identity_signals):
    assert live_identity(live_identity_signals, geometry_valid=True).live
    live_identity_signals["spectator_detector_checked"] = False
    assert not live_identity(live_identity_signals, geometry_valid=True).live


@pytest.mark.parametrize("shift", [(5, 10), (12, 15), (20, 20)])
def test_displaced_panel_is_unknown_and_never_live(panel_images, live_identity_signals, shift):
    positive, _ = panel_images(160, 126)
    gray = cv2.cvtColor(positive, cv2.COLOR_BGR2GRAY)
    labels = panel_components(gray)
    assert labels is not None
    moved = cv2.warpAffine(
        gray, np.float32([[1, 0, shift[0]], [0, 1, shift[1]]]), (160, 126), borderValue=60
    )
    result = detect_panel(moved, labels)
    assert result["checked"] is False
    assert result["panel_present"] is None
    assert result["reason"] in {"panel_structure_mismatch", "panel_structure_ambiguous"}
    live_identity_signals.update(
        spectator_detector_checked=result["checked"],
        spectator_panel_present=result["panel_present"],
        spectator_panel_absent=False,
    )
    assert not live_identity(live_identity_signals, geometry_valid=True).live
