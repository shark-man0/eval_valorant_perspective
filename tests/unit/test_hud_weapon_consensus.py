import copy
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.hud.weapon_consensus import (
    MATCHER,
    consensus_score,
    persistent_reference,
)

PROJECT = Path(__file__).resolve().parents[2]
LAYOUT = json.loads(
    (PROJECT / "config" / "hud_layout_1080p_v3.json").read_text(encoding="utf-8")
)
WEAPON_SPEC = LAYOUT["identity_structure_regions"]["weapon_ammo_structure"]
CROP_SHAPE = (178, 230)
NEIGHBOR_BOUNDS = [[0.0, 0.0, 0.18, 0.55]]


def _pixel_box(box, shape=CROP_SHAPE):
    height, width = shape
    return tuple(
        round(value * (width if axis % 2 == 0 else height))
        for axis, value in enumerate(box)
    )


def weapon_crop(
    index=0,
    *,
    slot=True,
    value=None,
    background_seed=None,
    underline=False,
    hide_feature=None,
    contradict_cap=False,
    neighbor_detail=False,
    generic=None,
):
    """Synthetic HUD crop: persistent cap/neck/leg ridges, dynamic ammo and scene."""
    height, width = CROP_SHAPE
    yy, xx = np.mgrid[:height, :width]
    background = (
        39.0
        + 0.045 * xx
        + 0.07 * yy
        + 3.4 * np.sin(xx / 19.0)
        + 2.6 * np.cos(yy / 13.0)
    )
    rng = np.random.default_rng(index if background_seed is None else background_seed)
    background += rng.normal(0.0, 1.4, CROP_SHAPE)
    crop = np.clip(background, 0, 255).astype(np.uint8)
    # A separately changing scene texture sits behind the fixed UI geometry.
    crop[18:93, 8:48] = np.clip(
        crop[18:93, 8:48].astype(np.int16)
        + rng.integers(-14, 15, size=(75, 40)),
        0,
        255,
    ).astype(np.uint8)

    if neighbor_detail:
        cv2.line(crop, (4, 14), (36, 82), 238, 3, cv2.LINE_AA)
        cv2.rectangle(crop, (7, 20), (34, 49), 190, 2)

    if slot:
        # Three separated vertical slot ridges sit in the static center corridor.
        # Their repeated top/bottom strokes leave a small gap like the source HUD.
        slot_x = {"cap": 122, "neck": 131, "leg": 140}
        for name, x in slot_x.items():
            if hide_feature == name:
                continue
            cv2.line(crop, (x, 112), (x, 120), 225, 1, cv2.LINE_8)
            cv2.line(crop, (x, 122), (x, 143), 225, 1, cv2.LINE_8)
            cv2.line(crop, (x - 1, 112), (x + 2, 112), 180, 1, cv2.LINE_8)
        if contradict_cap:
            cv2.line(crop, (122, 108), (122, 145), 242, 2, cv2.LINE_8)
    if generic == "horizontal":
        cv2.line(crop, (60, 159), (176, 159), 225, 2, cv2.LINE_AA)
    elif generic == "separator":
        cv2.line(crop, (132, 107), (132, 164), 225, 2, cv2.LINE_AA)
    if underline:
        # Noncritical rail detail is deliberately inconsistent across training frames.
        cv2.line(crop, (64, 159), (173, 159), 230, 2, cv2.LINE_AA)
    if value is None:
        value = ("30", "21", "9", "0")[index % 4]
    cv2.putText(crop, str(value), (67, 136), cv2.FONT_HERSHEY_SIMPLEX, 0.72, 248, 2, cv2.LINE_AA)
    return crop


def accepted_reference(frames, neighbor_bounds=None):
    stats = {}
    result = persistent_reference(frames, WEAPON_SPEC, stats, neighbor_bounds or [])
    return result, stats


def _write_png(path, image):
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(encoded.tobytes())


def _profile_for_reference(tmp_path, *, corrupt_allowed=False):
    result, _stats = accepted_reference([weapon_crop(i) for i in range(16)], NEIGHBOR_BOUNDS)
    assert result is not None
    reference, bounds, mask, regions, allowed = result
    _write_png(tmp_path / "weapon.png", reference)
    _write_png(tmp_path / "mask.png", mask)
    _write_png(tmp_path / "regions.png", regions)
    if corrupt_allowed:
        _write_png(tmp_path / "allowed.png", np.full((3, 4), 255, np.uint8))
    else:
        _write_png(tmp_path / "allowed.png", allowed)
    layout_path = tmp_path / "layout.json"
    layout_path.write_text(
        json.dumps(
            {
                "schema_version": "3.0",
                "profile_id": "weapon-consensus-test",
                "reference_resolution": {"width": CROP_SHAPE[1], "height": CROP_SHAPE[0]},
                "coordinate_policy": {},
                "rois": {"ammo_current_weapon": {"norm": [0, 0, 1, 1], "px": None}},
                "calibration_policy": {"required_anchors": []},
            }
        ),
        encoding="utf-8",
    )
    sidecar = tmp_path / "layout.templates.json"
    signal = {
        "roi": "ammo_current_weapon",
        "template": "weapon.png",
        "roi_bounds": bounds,
        "mask": "mask.png",
        "support_regions": "regions.png",
        "allowed_regions": "allowed.png",
        "matcher": MATCHER,
        "threshold": 0.90,
    }
    if corrupt_allowed == "missing":
        signal["allowed_regions"] = "missing.png"
    sidecar.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "anchors": {},
                "readers": {},
                "signals": {"weapon_ammo_structure": signal},
            }
        ),
        encoding="utf-8",
    )
    return sidecar, layout_path


def crop_to_bounds(image, bounds):
    x1, y1, x2, y2 = _pixel_box(bounds)
    return image[y1:y2, x1:x2]


def consensus(reference_result, image, diagnostics=None):
    reference, bounds, mask, regions, allowed = reference_result
    return consensus_score(
        reference,
        crop_to_bounds(image, bounds),
        mask,
        regions,
        allowed,
        diagnostics=diagnostics,
    )


def test_config_uses_persistent_weapon_slots_without_legacy_support_boxes():
    spec = copy.deepcopy(WEAPON_SPEC)
    assert spec["discovery"] == "persistent_slots_v1"
    assert "support_bounds" not in spec


def test_persistent_slot_consensus_survives_digits_and_world_texture_changes():
    frames = [weapon_crop(i, value=("100", "80", "48", "22")[i % 4]) for i in range(16)]
    result, stats = accepted_reference(frames, NEIGHBOR_BOUNDS)
    assert result is not None
    reference, bounds, mask, regions, allowed = result
    assert stats["matcher"] == MATCHER
    assert reference.dtype == mask.dtype == regions.dtype == allowed.dtype == np.uint8
    assert stats["training_accept_count"] >= 3
    assert stats["holdout_accept_count"] >= 3
    selected = stats["selected_candidate"]
    assert selected["consensus_contributor_count"] >= 3
    subfeatures = selected["learned_subfeatures"]
    assert 2 <= len(subfeatures) <= 4
    intended_pixels = np.zeros(CROP_SHAPE, np.uint8)
    x1, y1, x2, y2 = _pixel_box(WEAPON_SPEC["intended_bounds"])
    intended_pixels[y1:y2, x1:x2] = 255
    excluded = [*WEAPON_SPEC["dynamic_bounds"], *NEIGHBOR_BOUNDS]
    for box in (feature["normalized_bounds"] for feature in subfeatures):
        bx1, by1, bx2, by2 = _pixel_box(box)
        assert np.all(intended_pixels[by1:by2, bx1:bx2] == 255)
        for ex1, ey1, ex2, ey2 in excluded:
            assert bx2 / CROP_SHAPE[1] <= ex1 or bx1 / CROP_SHAPE[1] >= ex2 or (
                by2 / CROP_SHAPE[0] <= ey1 or by1 / CROP_SHAPE[0] >= ey2
            )
    for index in range(4):
        image = weapon_crop(40 + index, value=("100", "80", "48", "22")[index])
        assert consensus(result, image) >= 0.90
    # The reference is a frozen crop-bounded representation, not raw ammo text.
    intended = WEAPON_SPEC["intended_bounds"]
    assert abs(bounds[0] - intended[0]) <= 1 / CROP_SHAPE[1]
    assert abs(bounds[1] - intended[1]) <= 1 / CROP_SHAPE[0]
    assert abs(bounds[2] - intended[2]) <= 1 / CROP_SHAPE[1]
    assert abs(bounds[3] - intended[3]) <= 1 / CROP_SHAPE[0]
    assert mask.shape == regions.shape == allowed.shape == reference.shape[:2]


def test_partial_noncritical_underline_obscuration_keeps_consensus():
    frames = [weapon_crop(i, underline=(i % 4 == 0)) for i in range(16)]
    result, _stats = accepted_reference(frames, NEIGHBOR_BOUNDS)
    assert result is not None
    visible = weapon_crop(41, underline=True)
    partially_obscured = visible.copy()
    partially_obscured[160:165, 114:152] = 42
    assert consensus(result, visible) >= 0.90
    assert consensus(result, partially_obscured) >= 0.90


def test_hiding_all_three_critical_slot_features_is_unknown():
    frames = [weapon_crop(i) for i in range(16)]
    result, _stats = accepted_reference(frames, NEIGHBOR_BOUNDS)
    assert result is not None
    hidden = weapon_crop(41, slot=False)
    diagnostics = {}
    assert consensus(result, hidden, diagnostics) < 0.90
    assert all(group["unobservable"] for group in diagnostics["groups"])


def test_observable_contradictory_slot_is_not_presence():
    frames = [weapon_crop(i) for i in range(16)]
    result, _stats = accepted_reference(frames, NEIGHBOR_BOUNDS)
    assert result is not None
    contradiction = weapon_crop(44, hide_feature="cap", contradict_cap=True)
    assert float(contradiction.std()) > 10
    diagnostics = {}
    assert consensus(result, contradiction, diagnostics) < 0.90
    assert any(group["contradictory"] for group in diagnostics["groups"])


def test_crossing_edge_without_slot_cannot_match_frozen_reference():
    result, _stats = accepted_reference([weapon_crop(i) for i in range(16)], NEIGHBOR_BOUNDS)
    assert result is not None
    no_slot = weapon_crop(41, slot=False)
    _reference, bounds, _mask, regions, _allowed = result
    bx1, by1, _bx2, _by2 = _pixel_box(bounds)
    for group in range(1, int(regions.max()) + 1):
        ys, xs = np.where(regions == group)
        x = bx1 + int(np.median(xs))
        cv2.line(
            no_slot,
            (x, by1 + int(ys.min()) - 2),
            (x, by1 + int(ys.max()) + 2),
            235,
            2,
            cv2.LINE_8,
        )
    diagnostics = {}
    assert consensus(result, no_slot, diagnostics) < 0.90
    assert any(group["contradictory"] for group in diagnostics["groups"])


def test_small_background_and_brightness_changes_inside_support_keep_slot_positive():
    result, _stats = accepted_reference([weapon_crop(i) for i in range(16)], NEIGHBOR_BOUNDS)
    assert result is not None
    changed = weapon_crop(42)
    x1, y1, x2, y2 = _pixel_box(WEAPON_SPEC["intended_bounds"])
    yy, xx = np.mgrid[y1:y2, x1:x2]
    drift = (7.0 + 0.025 * (xx - x1) + 0.035 * (yy - y1)).astype(np.int16)
    changed[y1:y2, x1:x2] = np.clip(
        changed[y1:y2, x1:x2].astype(np.int16) + drift, 0, 255
    ).astype(np.uint8)
    assert consensus(result, changed) >= 0.90


@pytest.mark.parametrize("kind", ["ability_neighbor", "horizontal", "separator", "background"])
def test_non_slot_patterns_never_create_a_weapon_reference(kind):
    if kind == "ability_neighbor":
        frames = [weapon_crop(i, slot=False, neighbor_detail=True) for i in range(16)]
    elif kind in {"horizontal", "separator"}:
        frames = [weapon_crop(i, slot=False, generic=kind) for i in range(16)]
    else:
        frames = [weapon_crop(i, slot=False) for i in range(16)]
    result, _stats = accepted_reference(frames, NEIGHBOR_BOUNDS)
    assert result is None


def test_training_consensus_uses_multiple_independent_frames():
    frames = [weapon_crop(i) for i in range(16)]
    assert len({frame.tobytes() for frame in frames}) >= 12
    result, stats = accepted_reference(frames, NEIGHBOR_BOUNDS)
    assert result is not None
    assert stats["training_accept_count"] >= 3
    assert stats["holdout_accept_count"] >= 3


def test_holdout_variation_cannot_change_training_selected_reference():
    training = [weapon_crop(i) for i in range(8)]
    holdouts_a = [weapon_crop(30 + i, underline=(i % 2 == 0)) for i in range(8)]
    holdouts_b = [
        weapon_crop(70 + i, underline=(i % 2 != 0), background_seed=800 + i)
        for i in range(8)
    ]
    frames_a = [sample for pair in zip(training, holdouts_a, strict=True) for sample in pair]
    frames_b = [sample for pair in zip(training, holdouts_b, strict=True) for sample in pair]
    result_a, _stats_a = accepted_reference(frames_a, NEIGHBOR_BOUNDS)
    result_b, _stats_b = accepted_reference(frames_b, NEIGHBOR_BOUNDS)
    assert result_a is not None and result_b is not None
    for first, second in zip(result_a, result_b, strict=True):
        if isinstance(first, np.ndarray):
            assert np.array_equal(first, second)
        else:
            assert first == second


def test_failing_holdout_rejects_training_proposal():
    training = [weapon_crop(i) for i in range(8)]
    blank = np.full(CROP_SHAPE, 42, dtype=np.uint8)
    frames = [sample for pair in zip(training, [blank] * 8, strict=True) for sample in pair]
    result, stats = accepted_reference(frames, NEIGHBOR_BOUNDS)
    assert result is None
    assert stats["reason"] in {"persistent_slots_insufficient", "holdout_rejected"}


def test_loaded_weapon_consensus_profile_dispatches_to_dedicated_matcher(tmp_path):
    sidecar, layout_path = _profile_for_reference(tmp_path)
    profile = HudTemplateProfile.load(sidecar)
    assert not profile.reader_diagnostics
    signals = profile.detect_signals(weapon_crop(40), HudLayout.load(layout_path))
    assert signals["weapon_ammo_structure"] is True
    assert signals["weapon_ammo_structure_confidence"] >= 0.90


@pytest.mark.parametrize("corrupt_allowed", [True, "missing"])
def test_invalid_or_missing_consensus_allowed_asset_fails_closed(tmp_path, corrupt_allowed):
    sidecar, layout_path = _profile_for_reference(tmp_path, corrupt_allowed=corrupt_allowed)
    profile = HudTemplateProfile.load(sidecar)
    assert any("weapon_ammo_structure" in note for note in profile.reader_diagnostics)
    signals = profile.detect_signals(weapon_crop(40), HudLayout.load(layout_path))
    assert "weapon_ammo_structure" not in signals
