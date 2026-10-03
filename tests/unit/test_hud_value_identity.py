import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from scripts.e2e.calibration_report import sanitize_calibration
from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.hud.value_identity import (
    MATCHER,
    scaffold_reference,
    support_regions,
    value_invariant_score,
)
from valorant_ai_coach.resources import resource_path

PROJECT = Path(__file__).resolve().parents[2]
LAYOUT = json.loads(
    (PROJECT / "config" / "hud_layout_1080p_v3.json").read_text(encoding="utf-8")
)
# Pin the original two-box weapon proposal here. That algorithm is now tested as
# a legacy matcher and must remain stable when the production config switches to
# the role-specific consensus proposal.
LEGACY_WEAPON_SPEC = {
    "intended_bounds": [0.24, 0.59, 0.78, 0.93],
    "support_bounds": [[0.515, 0.62, 0.635, 0.79], [0.25, 0.82, 0.77, 0.92]],
    "dynamic_bounds": [[0.25, 0.59, 0.51, 0.82], [0.64, 0.59, 0.78, 0.82]],
}
SPECS = {**LAYOUT["identity_structure_regions"], "weapon_ammo_structure": LEGACY_WEAPON_SPEC}
ROLE_SHAPES = {"hp_hud_structure": (153, 220), "weapon_ammo_structure": (178, 230)}


def _pixel_box(box, shape):
    height, width = shape
    return tuple(
        round(value * (width if axis % 2 == 0 else height))
        for axis, value in enumerate(box)
    )


def scaffold_crop(role, value_index=0, *, scaffold=True, line_only=False, outside_noise=False):
    spec = SPECS[role]
    height, width = ROLE_SHAPES[role]
    image = np.full((height, width), 42, dtype=np.uint8)
    if scaffold:
        for group, bounds in enumerate(spec["support_bounds"], start=1):
            x1, y1, x2, y2 = _pixel_box(bounds, image.shape)
            if role == "hp_hud_structure" and group == 1:
                cv2.line(image, (x1 + 4, (y1 + y2) // 2), (x2 - 4, (y1 + y2) // 2), 210, 2)
            elif role == "hp_hud_structure" and group == 2:
                cv2.line(image, (x1 + 5, y1 + 6), (x2 - 5, y2 - 7), 220, 2)
                cv2.line(image, (x1 + 9, y1 + 6), (x2 - 1, y2 - 7), 150, 1)
                cv2.line(image, (x1 + 7, y1 + 8), (x1 + 7, y1 + 20), 190, 2)
            elif role == "weapon_ammo_structure" and group == 1:
                cv2.rectangle(image, (x1 + 4, y1 + 4), (x2 - 5, y2 - 5), 220, 1)
                cv2.line(image, (x1 + 5, y1 + 7), (x2 - 6, y2 - 7), 190, 1)
                cv2.line(image, (x1 + 5, y2 - 7), (x2 - 6, y1 + 7), 190, 1)
            elif role == "weapon_ammo_structure" and group == 2:
                # Three separated, abstract angular marks form a persistent HUD rail.
                for offset in (8, 42, 79):
                    start_x = x1 + offset
                    if start_x + 18 < x2 - 2:
                        cv2.line(image, (start_x, y1 + 5), (start_x + 8, y1 + 5), 220, 1)
                        cv2.line(image, (start_x + 8, y1 + 5), (start_x + 14, y2 - 5), 220, 1)
                        cv2.line(image, (start_x + 14, y2 - 5), (start_x + 18, y2 - 5), 220, 1)
    elif line_only:
        x1, y1, x2, y2 = _pixel_box(spec["support_bounds"][0], image.shape)
        cv2.line(image, (x1 + 2, (y1 + y2) // 2), (x2 - 2, (y1 + y2) // 2), 220, 2)
    if outside_noise:
        # Bright unrelated detail stays outside the role's intended scaffold bounds.
        cv2.putText(image, "A7", (2, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 255, 2)
        cv2.line(image, (4, 62), (21, 36), 245, 2)
    if role == "hp_hud_structure":
        cv2.putText(
            image,
            ("100", "80", "48", "22")[value_index % 4],
            (81, 112),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            240,
            2,
            cv2.LINE_AA,
        )
    else:
        cv2.putText(
            image,
            ("30", "21", "9", "0")[value_index % 4],
            (66, 135),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            240,
            2,
            cv2.LINE_AA,
        )
    return image


def selected(role, frames, *, neighbor_bounds=None):
    stats = {}
    result = scaffold_reference(frames, SPECS[role], stats, neighbor_bounds or [])
    return result, stats


def score_crop(reference, crop, bounds, mask, regions):
    x1, y1, x2, y2 = _pixel_box(bounds, crop.shape)
    return value_invariant_score(reference, crop[y1:y2, x1:x2], mask, regions)


@pytest.mark.parametrize("role", ["hp_hud_structure", "weapon_ammo_structure"])
def test_role_scaffold_survives_hp_and_ammo_glyph_changes(role):
    frames = [scaffold_crop(role, index) for index in range(16)]
    result, stats = selected(role, frames)
    assert result is not None
    reference, bounds, mask, regions = result
    assert stats["matcher"] == MATCHER
    assert stats["reason"] == "selected"
    assert stats["training_accept_count"] >= 3
    assert stats["holdout_accept_count"] >= 3
    assert np.all(reference[regions == 0] == 0)
    for value_index in range(4):
        assert score_crop(reference, frames[value_index], bounds, mask, regions) >= 0.90


def test_support_mask_is_role_relative_and_stays_inside_intended_bounds():
    role = "weapon_ammo_structure"
    crop_shape = ROLE_SHAPES[role]
    spec = SPECS[role]
    groups = support_regions(crop_shape, spec, [])
    intended = _pixel_box(spec["intended_bounds"], crop_shape)
    ys, xs = np.nonzero(groups)
    assert xs.min() >= intended[0] and xs.max() < intended[2]
    assert ys.min() >= intended[1] and ys.max() < intended[3]
    assert set(np.unique(groups)) == {0, 1, 2}
    result, _ = selected(role, [scaffold_crop(role, i) for i in range(16)])
    assert result is not None
    reference, bounds, mask, regions = result
    assert reference.shape == mask.shape == regions.shape
    assert set(np.unique(regions)) == {0, 1, 2}
    assert not np.any(mask[regions == 0])
    assert all(np.count_nonzero(mask[regions == group]) >= 32 for group in (1, 2))
    x1, y1, x2, y2 = _pixel_box(bounds, crop_shape)
    assert bounds[0] >= spec["intended_bounds"][0]
    assert bounds[1] >= spec["intended_bounds"][1]
    assert bounds[2] <= spec["intended_bounds"][2]
    assert bounds[3] <= spec["intended_bounds"][3]
    assert x2 > x1 and y2 > y1


@pytest.mark.parametrize("role", ["hp_hud_structure", "weapon_ammo_structure"])
def test_numeric_only_and_nearby_text_cannot_create_a_reference(role):
    values_only = [scaffold_crop(role, i, scaffold=False) for i in range(16)]
    result, stats = selected(role, values_only)
    assert result is None
    assert stats["reason"] == "scaffold_evidence_insufficient"
    nearby_text = [scaffold_crop(role, i, scaffold=False, outside_noise=True) for i in range(16)]
    result, _ = selected(role, nearby_text)
    assert result is None


def test_single_horizontal_line_and_ability_like_detail_are_not_a_weapon_scaffold():
    role = "weapon_ammo_structure"
    line_frames = [scaffold_crop(role, i, scaffold=False, line_only=True) for i in range(16)]
    result, _ = selected(role, line_frames)
    assert result is None
    # Detail outside the intended role may not supply the missing second support group.
    other_role_frames = [
        scaffold_crop(role, i, scaffold=False, outside_noise=True) for i in range(16)
    ]
    result, _ = selected(role, other_role_frames)
    assert result is None


def test_neighbor_content_is_excluded_before_reference_and_score():
    role = "weapon_ammo_structure"
    neighbor = [0.0, 0.0, 0.10, 0.35]
    clean = [scaffold_crop(role, i) for i in range(16)]
    noisy = [scaffold_crop(role, i, outside_noise=True) for i in range(16)]
    clean_result, clean_stats = selected(role, clean, neighbor_bounds=[neighbor])
    noisy_result, noisy_stats = selected(role, noisy, neighbor_bounds=[neighbor])
    assert clean_result is not None and noisy_result is not None
    cref, cbounds, cmask, cregions = clean_result
    nref, nbounds, nmask, nregions = noisy_result
    assert cbounds == nbounds
    assert np.array_equal(cregions, nregions)
    assert np.array_equal(cmask, nmask)
    assert np.array_equal(cref, nref)
    assert (
        clean_stats["selected_candidate"]["roi_bounds"]
        == noisy_stats["selected_candidate"]["roi_bounds"]
    )
    for i in (0, 1, 2, 3):
        assert score_crop(nref, noisy[i], nbounds, nmask, nregions) >= 0.90


def test_holdout_is_validation_only_and_blank_holdout_rejects():
    role = "weapon_ammo_structure"
    training = [scaffold_crop(role, i) for i in range(8)]
    blank = np.full_like(training[0], 42)
    random = np.random.default_rng(211).integers(0, 256, training[0].shape, dtype=np.uint8)
    holdout_blank = [training[i // 2] if i % 2 == 0 else blank for i in range(16)]
    holdout_noise = [training[i // 2] if i % 2 == 0 else random for i in range(16)]
    blank_result, blank_stats = selected(role, holdout_blank)
    noise_result, noise_stats = selected(role, holdout_noise)
    assert blank_result is None and noise_result is None
    assert blank_stats["reason"] == noise_stats["reason"] == "holdout_rejected"
    assert blank_stats["holdout_accept_count"] == noise_stats["holdout_accept_count"] == 0
    assert blank_stats["training_accept_count"] == noise_stats["training_accept_count"]
    assert (
        blank_stats["selected_candidate"]["roi_bounds"]
        == noise_stats["selected_candidate"]["roi_bounds"]
    )
    assert (
        blank_stats["selected_candidate"]["training_similarity"]
        == noise_stats["selected_candidate"]["training_similarity"]
    )


def test_malformed_overlapping_support_groups_fail_closed():
    role = "weapon_ammo_structure"
    spec = json.loads(json.dumps(SPECS[role]))
    spec["support_bounds"][1] = list(spec["support_bounds"][0])
    stats = {}
    result = scaffold_reference([scaffold_crop(role, i) for i in range(16)], spec, stats, [])
    assert result is None
    assert stats["reason"] == "role_geometry_invalid"


def _write_profile_assets(tmp_path, *, support_mode="valid"):
    role = "weapon_ammo_structure"
    frames = [scaffold_crop(role, index) for index in range(16)]
    stats = {}
    result = scaffold_reference(frames, SPECS[role], stats, [])
    assert result is not None
    reference, bounds, mask, regions = result

    asset_dir = tmp_path / "identity"
    asset_dir.mkdir(exist_ok=True)
    template_path = asset_dir / "weapon.png"
    mask_path = asset_dir / "weapon.mask.png"
    support_path = asset_dir / "weapon.support.png"
    assert cv2.imwrite(str(template_path), reference)
    assert cv2.imwrite(str(mask_path), mask)
    if support_mode == "valid":
        assert cv2.imwrite(str(support_path), regions)
    elif support_mode == "single_group":
        assert cv2.imwrite(str(support_path), np.where(regions > 0, 1, 0).astype(np.uint8))
    elif support_mode == "shape_mismatch":
        assert cv2.imwrite(str(support_path), regions[:-1])

    profile_path = tmp_path / "hud_layout.templates.json"
    raw = {
        "schema_version": "1.0",
        "anchors": {},
        "readers": {},
        "signals": {
            role: {
                "roi": "ammo_current_weapon",
                "roi_bounds": bounds,
                "template": "identity/weapon.png",
                "threshold": 0.90,
                "mask": "identity/weapon.mask.png",
                "support_regions": "identity/weapon.support.png",
                "matcher": MATCHER,
            }
        },
    }
    return HudTemplateProfile(profile_path, raw), reference, mask, regions, bounds, frames


def _full_frame_with_weapon_crop(layout, crop):
    width, height = layout.reference_resolution
    frame = np.full((height, width, 3), 42, dtype=np.uint8)
    x1, y1, x2, y2 = layout.normalized_roi("ammo_current_weapon").pixel_bounds(width, height)
    assert (y2 - y1, x2 - x1) == crop.shape
    frame[y1:y2, x1:x2] = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    return frame


def test_profile_loader_uses_value_invariant_matcher_for_signal_detection(tmp_path):
    profile, _reference, _mask, _regions, _bounds, frames = _write_profile_assets(tmp_path)
    layout = HudLayout.load(resource_path("config/hud_layout_1080p_v3.json"))

    for index in range(4):
        frame = _full_frame_with_weapon_crop(layout, frames[index])
        signals = profile.detect_signals(frame, layout)
        assert signals["weapon_ammo_structure"] is True
        assert signals["weapon_ammo_structure_confidence"] >= 0.90


@pytest.mark.parametrize("support_mode", ["missing", "single_group", "shape_mismatch"])
def test_invalid_support_assets_stay_unknown_without_legacy_fallback(tmp_path, support_mode):
    profile, _reference, _mask, _regions, _bounds, frames = _write_profile_assets(
        tmp_path, support_mode=support_mode
    )
    layout = HudLayout.load(resource_path("config/hud_layout_1080p_v3.json"))
    frame = _full_frame_with_weapon_crop(layout, frames[0])

    signals = profile.detect_signals(frame, layout)

    assert "weapon_ammo_structure" not in signals
    assert "weapon_ammo_structure" not in profile._signal_templates
    assert any("signal weapon_ammo_structure:" in note for note in profile.reader_diagnostics)


def test_shared_calibration_keeps_value_identity_numbers_and_drops_private_fields():
    stats = {
        "matcher": MATCHER,
        "mask_content_hash": "a" * 64,
        "support_content_hash": "b" * 64,
        "template_path": "PRIVATE_TEMPLATE_PATH",
        "selected_candidate": {
            "proposal_source": "configured_role_scaffold",
            "roi_bounds": [0.25, 0.62, 0.77, 0.92],
            "intended_bounds": [0.24, 0.59, 0.78, 0.93],
            "support_bounds": [[0.515, 0.62, 0.635, 0.79], [0.25, 0.82, 0.77, 0.92]],
            "dynamic_bounds": [[0.25, 0.59, 0.51, 0.82]],
            "training_accept_count": 8,
            "holdout_accept_count": 8,
            "mask_population": 180,
            "group_mask_population": [70, 110],
            "training_similarity": {"count": 8, "min": 0.98, "median": 1.0, "max": 1.0},
            "holdout_similarity": {"count": 8, "min": 0.96, "median": 0.99, "max": 1.0},
            "structural_gates": {"line_support": True, "arrangement": True},
            "private_text": "PRIVATE_GLYPH_TEXT",
            "glyph_values": ["100", "80", "48", "22"],
            "asset_path": "PRIVATE_ASSET_PATH",
        },
    }
    report = sanitize_calibration(
        {
            "schema_version": 1,
            "automatic_identity_generation": {
                "version": 2,
                "references": {"weapon_ammo_structure": stats},
            },
        }
    )
    generation = report["automatic_identity_generation"]["references"][
        "weapon_ammo_structure"
    ]["value_invariant_generation"]
    selected_candidate = generation["selected_candidate"]
    encoded = json.dumps(report)

    assert generation["matcher"] == MATCHER
    assert selected_candidate["training_accept_count"] == 8
    assert selected_candidate["holdout_accept_count"] == 8
    assert selected_candidate["group_mask_population"] == [70, 110]
    assert selected_candidate["training_similarity"]["median"] == 1.0
    assert generation["mask_content_hash"] == "a" * 64
    assert generation["support_content_hash"] == "b" * 64
    assert "PRIVATE_" not in encoded
    assert "glyph_values" not in encoded


