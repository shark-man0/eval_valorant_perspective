import json

import cv2
import numpy as np
import pytest
from test_hud_weapon_stability import frames

from scripts.e2e.calibration_report import sanitize_calibration
from valorant_ai_coach.hud.identity import live_identity
from valorant_ai_coach.hud.spectator import detect_panel, generate_panel_reference, panel_components
from valorant_ai_coach.hud.weapon_identity import edge_features, structural_score, weapon_reference


def test_weapon_survives_brightness_jpeg_and_noise_without_stable_intensities():
    rng = np.random.default_rng(9)
    images = []
    for index, frame in enumerate(frames()):
        image = np.clip(
            frame.astype(float) + index % 8 * 6 + rng.normal(0, 3, frame.shape), 0, 255
        ).astype(np.uint8)
        success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 65])
        assert success
        images.append(cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE))
    stats = {}
    result = weapon_reference(images, stats)
    assert result is not None
    reference, bounds, mask = result
    selected = stats["selected_candidate"]
    assert selected["stable_pixel_ratio"] < 0.10  # Old variance<=4 would erase this mask.
    assert selected["mask_population"] >= 32
    assert selected["orientation_consistency"] >= 0.90
    assert stats["holdout_accept_count"] >= 3
    assert stats["matcher"] == "oriented_edges_v1"
    assert structural_score(reference, reference, mask) >= 0.90
    assert selected["training_similarity"]["median"] >= 0.90
    assert selected["holdout_similarity"]["median"] >= 0.90
    assert len(bounds) == 4


def test_weapon_displacement_occlusion_and_wrong_structure_stay_unknown():
    reference, _, mask = weapon_reference(frames(), {})
    shifted = cv2.warpAffine(reference, np.float32([[1, 0, 5], [0, 1, 5]]), reference.shape[::-1])
    assert structural_score(reference, shifted, mask) < 0.90
    assert structural_score(reference, np.full_like(reference, 70), mask) == 0
    assert structural_score(reference, np.flipud(reference), mask) < 0.90
    assert structural_score(reference, cv2.GaussianBlur(reference, (15, 15), 5), mask) < 0.90


def test_one_pixel_edge_jitter_is_tolerated_but_clutter_is_penalized():
    reference = np.full((60, 64), 50, np.uint8)
    cv2.rectangle(reference, (10, 10), (48, 45), 200, 2)
    mask = edge_features(reference)[0].astype(np.uint8) * 255
    jitter = cv2.warpAffine(reference, np.float32([[1, 0, 1], [0, 1, 0]]), (64, 60), borderValue=50)
    assert structural_score(reference, jitter, mask) >= 0.90
    clutter = reference.copy()
    for y in range(12, 44, 3):
        cv2.line(clutter, (7, y), (14, y + 2), 240, 1)
    assert structural_score(reference, clutter, mask) < 0.90


def test_fragmented_anti_aliased_portrait_is_not_required_to_be_closed(panel_images):
    positive, negative = panel_images(160, 126)
    broken = positive.copy()
    # Remove part of one side: no clean convex 4-vertex contour remains.
    broken[45:67, 8:14] = 60
    broken[27:89, 7:49] = cv2.GaussianBlur(broken[27:89, 7:49], (3, 3), 0.5)
    diag = {}
    labels = panel_components(cv2.cvtColor(broken, cv2.COLOR_BGR2GRAY), diag)
    assert labels is not None
    assert diag["portrait_supported_count"] > 0
    assert diag["portrait_frame_score"] >= 0.70
    stats = {}
    learned = generate_panel_reference(
        [broken if i % 4 < 2 else negative for i in range(32)], stats
    )
    assert learned is not None
    assert detect_panel(broken, learned)["panel_present"] is True


@pytest.mark.parametrize("missing", ["boundary", "portrait", "text"])
def test_portrait_alone_or_missing_compound_evidence_cannot_generate_panel(missing, panel_images):
    positive, _ = panel_images(160, 126)
    if missing == "boundary":
        positive[:20] = 60
    elif missing == "portrait":
        positive[25:90, :50] = 60
    else:
        positive[25:90, 50:] = 60
    assert panel_components(cv2.cvtColor(positive, cv2.COLOR_BGR2GRAY)) is None
    assert generate_panel_reference([positive] * 32, {}) is None


@pytest.mark.parametrize("kind", ["normal", "buy", "remote", "map"])
def test_backgrounds_cannot_generate_positive_panel(kind, panel_images, live_identity_signals):
    positive, image = panel_images(160, 126)
    image = image.copy()
    if kind == "buy":
        for y in (20, 60):
            for x in (10, 55, 100):
                cv2.rectangle(image, (x, y), (x + 35, y + 30), (200, 200, 200), 1)
    elif kind == "remote":
        cv2.circle(image, (80, 63), 25, (220, 220, 220), 1)
        cv2.line(image, (30, 63), (130, 63), (200, 200, 200), 1)
    elif kind == "map":
        for offset in (10, 35, 60):
            cv2.line(image, (offset, 20), (offset + 65, 105), (230, 230, 230), 2)
    assert panel_components(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)) is None
    assert generate_panel_reference([image] * 32, {}) is None
    if kind != "normal":
        blocker = {
            "buy": "buy_menu_grid_present",
            "remote": "remote_control_candidate",
            "map": "expanded_map_stable",
        }[kind]
        live_identity_signals[blocker] = True
        if kind == "buy":
            live_identity_signals["buy_menu_close_anchor_present"] = True
        assert not live_identity(live_identity_signals, geometry_valid=True).live
    labels = panel_components(cv2.cvtColor(positive, cv2.COLOR_BGR2GRAY))
    result = detect_panel(image, labels)
    assert result["panel_present"] is not True


def test_structural_diagnostics_sanitization():
    stats = {}
    weapon_reference(frames(), stats)
    selected = stats["selected_candidate"]
    selected["player"] = "PRIVATE"
    selected["training_similarity"]["path"] = "PRIVATE"
    raw = {
        "schema_version": 1,
        "automatic_identity_generation": {"references": {"weapon_ammo_structure": stats}},
    }
    report = sanitize_calibration(raw)
    shared = report["automatic_identity_generation"]["references"]["weapon_ammo_structure"][
        "weapon_ammo_generation"
    ]["selected_candidate"]
    assert "PRIVATE" not in json.dumps(report)
    assert shared["edge_count"] >= shared["mask_population"] >= 32
    assert shared["training_similarity"]["count"] == 16
    assert shared["orientation_consistency"] >= 0.90
