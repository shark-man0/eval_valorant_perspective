import json

import cv2
import numpy as np

from scripts.e2e.calibration_report import sanitize_calibration
from valorant_ai_coach.hud.spectator import generate_panel_reference, panel_components
from valorant_ai_coach.hud.weapon_identity import masked_score, weapon_reference


def frames():
    images = []
    for i in range(32):
        image = np.full((120, 160), 40, np.uint8)
        cv2.rectangle(image, (0, 0), (159, 119), 220, 2)
        cv2.line(image, (10, 10), (100, 100), 160, 2)
        cv2.putText(image, str(i), (4, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 240, 1)
        images.append(image)
    return images


def test_weapon_digits_reload_and_switch_do_not_require_ammo_value():
    stats = {}
    result = weapon_reference(frames(), stats)
    assert result is not None
    reference, bounds, mask = result
    # Reload/increased ammo and a switched weapon change digits/icons, not the frame.
    for value in ("99", "1", "30"):
        image = frames()[0]
        image[4:28, 3:25] = 40
        cv2.putText(image, value, (4, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 240, 1)
        x1, y1, x2, y2 = [round(v * (160 if i % 2 == 0 else 120)) for i, v in enumerate(bounds)]
        assert masked_score(reference, image[y1:y2, x1:x2], mask) >= 0.90
    assert stats["holdout_accept_count"] >= 3
    assert stats["selected_candidate"]["reason"] == "selected"
    assert masked_score(reference, np.zeros_like(reference), mask) == 0
    assert masked_score(reference, reference[::2], mask) == 0


def test_changing_world_texture_and_training_only_reference_are_rejected():
    random = np.random.default_rng(42)
    stats = {}
    assert (
        weapon_reference(
            [random.integers(0, 255, (120, 160), dtype=np.uint8) for _ in range(32)], stats
        )
        is None
    )
    texture = random.integers(0, 255, (120, 160), dtype=np.uint8)
    assert weapon_reference([texture] * 32, stats) is None
    stripes = np.full((120, 160), 40, np.uint8)
    stripes[::10] = 200
    assert weapon_reference([stripes] * 32, stats) is None
    mixed = [frame if i % 2 == 0 else np.zeros_like(frame) for i, frame in enumerate(frames())]
    assert weapon_reference(mixed, stats) is None
    assert stats["holdout_rejected"] == 1
    assert stats["holdout_accept_count"] == 0


def test_spectator_relative_layout_and_element_diagnostics(panel_images):
    positive, negative = panel_images(160, 126)
    gray = cv2.cvtColor(positive, cv2.COLOR_BGR2GRAY)
    # Boundary in the middle of a larger ROI: absolute top/bottom placement is irrelevant.
    canvas = np.full((240, 240), 60, np.uint8)
    canvas[65:191, 60:220] = gray
    diag = {}
    assert panel_components(canvas, diag) is not None
    assert diag["all_components"]
    stats = {}
    assert (
        generate_panel_reference([positive if i % 4 < 2 else negative for i in range(32)], stats)
        is not None
    )
    assert len(stats["samples"]) == 32
    assert stats["evidence_counts"]["all_components"] == 16
    assert stats["rejection_counts"]["structural_rejected"] == 16
    assert panel_components(np.zeros((100, 100), np.uint8), diag) is None
    assert diag["reason"] == "contrast_rejected"
    assert panel_components(cv2.GaussianBlur(gray, (31, 31), 12), diag) is None
    assert diag["reason"] == "blur_rejected"


def test_generation_diagnostics_share_only_allowlisted_statistics():
    stats = {}
    weapon_reference(frames(), stats)
    stats["candidates"][0]["image_path"] = "PRIVATE"
    stats["selected_candidate"]["OCR"] = "PRIVATE"
    stats["mask_content_hash"] = "b" * 64
    raw = {
        "schema_version": 1,
        "automatic_identity_generation": {
            "version": 2,
            "references": {
                "weapon_ammo_structure": stats,
                "spectator_panel": {
                    "samples": [{"sample_index": 0, "reason": "PRIVATE", "path": "PRIVATE"}]
                },
            },
        },
    }
    shared = sanitize_calibration(raw)
    encoded = json.dumps(shared)
    assert "PRIVATE" not in encoded
    weapon = shared["automatic_identity_generation"]["references"]["weapon_ammo_structure"][
        "weapon_ammo_generation"
    ]
    assert weapon["mask_content_hash"] == "b" * 64
    assert weapon["selected_candidate"]["holdout_accept_count"] >= 3
