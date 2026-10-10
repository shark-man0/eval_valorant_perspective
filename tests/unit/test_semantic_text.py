import hashlib
import json

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.semantic_text import SemanticPhaseContext, SemanticTextReference
from valorant_ai_coach.hud.templates import HudTemplateProfile


def _assets():
    image = np.random.default_rng(123).integers(20, 235, (40, 120), dtype=np.uint8)
    regions = np.zeros(image.shape, np.uint8)
    for group in (1, 2, 3):
        regions[5:35, (group - 1) * 40 + 5 : group * 40 - 5] = group
    mask = np.asarray(regions > 0, dtype=np.uint8) * 255
    training = [(f"{i:064x}", image.copy()) for i in range(3)]
    return image, mask, regions, training


def test_all_groups_must_match_and_background_is_not_evidence():
    image, mask, regions, training = _assets()
    reference = SemanticTextReference(image, mask, regions, training, 0.90)
    changed = image.copy()
    changed[mask == 0] = 255
    assert reference.score(changed) >= 0.90
    changed[regions == 3] = 100
    assert reference.score(changed) == 0
    assert reference.score(np.zeros((2, 3), np.uint8)) == 0
    assert reference.score(np.zeros_like(image)) == 0


@pytest.mark.parametrize("mutation", ["weak", "duplicate", "two", "bad_hash"])
def test_training_requires_three_distinct_supported_source_frames(mutation):
    image, mask, regions, training = _assets()
    if mutation == "weak":
        training[2] = (training[2][0], np.zeros_like(image))
    elif mutation == "duplicate":
        training[2] = training[0]
    elif mutation == "two":
        training = training[:2]
    else:
        training[2] = ("not-a-frame-hash", image)
    with pytest.raises(ValueError):
        SemanticTextReference(image, mask, regions, training, 0.90)


@pytest.mark.parametrize("threshold", [0.89, float("nan"), float("inf")])
def test_threshold_cannot_be_relaxed(threshold):
    image, mask, regions, training = _assets()
    with pytest.raises(ValueError, match="NCC"):
        SemanticTextReference(image, mask, regions, training, threshold)


def test_groups_cannot_repeat_the_same_spatial_support():
    image, mask, regions, training = _assets()
    regions[5:35, 5:35] = np.tile(np.array([1, 2, 3], np.uint8), (30, 10))
    with pytest.raises(ValueError, match="separate portions"):
        SemanticTextReference(image, mask, regions, training, 0.90)


def _profile(tmp_path, *, signal="buy_phase_template", roi="center_phase_banner", support=3):
    image, mask, regions, training = _assets()
    for name, value in [("ref.png", image), ("mask.png", mask), ("groups.png", regions)]:
        assert cv2.imwrite(str(tmp_path / name), value)
    exemplars = []
    for i, (frame_hash, pixels) in enumerate(training[:support]):
        name = f"train-{i}.png"
        assert cv2.imwrite(str(tmp_path / name), pixels)
        exemplars.append({"template": name, "frame_sha256": frame_hash})
    path = tmp_path / "profile.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "ocr_fallback_rois": [],
                "signals": {
                    signal: {
                        "matcher": "semantic_text_ncc_v1",
                        "roi": roi,
                        "roi_bounds": [0, 0, 1, 1],
                        "template": "ref.png",
                        "mask": "mask.png",
                        "support_regions": "groups.png",
                        "threshold": 0.90,
                        "training": exemplars,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    layout = HudLayout("1.0", True, (120, 40), {roi: NormalizedRoi(0, 0, 1, 1)})
    return path, layout, cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)


def test_profile_detects_presence_and_fingerprints_training_assets(tmp_path):
    path, layout, frame = _profile(tmp_path)
    profile = HudTemplateProfile.load(path)
    assert not profile.reader_diagnostics
    assert profile.detect_signals(frame, layout)["buy_phase_template"] is True
    assert "buy_phase_template" not in profile.detect_signals(np.zeros_like(frame), layout)
    layout_path = tmp_path / "layout.json"
    layout_path.write_text("{}", encoding="utf-8")
    before = profile.fingerprint(layout_path)
    (tmp_path / "train-2.png").write_bytes(b"changed")
    assert profile.fingerprint(layout_path) != before


@pytest.mark.parametrize("case", ["match", "flat_group", "wrong_text", "wrong_shape"])
def test_measurement_preserves_score_and_does_not_authorize_absence(case):
    image, mask, regions, training = _assets()
    reference = SemanticTextReference(image, mask, regions, training, 0.90)
    current = image.copy()
    if case == "flat_group":
        current[regions == 2] = 100
    elif case == "wrong_text":
        current[regions == 2] = 255 - current[regions == 2]
    elif case == "wrong_shape":
        current = current[:2, :3]
    result = reference.measure(current)
    assert result["score"] == reference.score(current)
    assert result["absence_checked"] is False
    assert result["runtime_transition_authorized"] is False
    if case == "flat_group":
        assert result["groups"][1]["reason"] == "contrast_unavailable"
    elif case == "wrong_text":
        assert result["groups"][1]["reason"] == "below_threshold"
    elif case == "wrong_shape":
        assert all(group["reason"] == "shape_mismatch" for group in result["groups"])


def test_profile_optional_measurements_preserve_signals_and_source_crop(tmp_path):
    path, layout, frame = _profile(tmp_path)
    profile = HudTemplateProfile.load(path)
    for pixels in (frame, np.zeros_like(frame)):
        records = {}
        plain = profile.detect_signals(pixels, layout)
        measured = profile.detect_signals(pixels, layout, semantic_diagnostics=records)
        assert measured == plain
        record = records["buy_phase_template"]
        assert record["pixel_bounds"] == [0, 0, 120, 40]
        assert record["crop_pixel_sha256"] == hashlib.sha256(pixels.tobytes()).hexdigest()
        assert record["absence_checked"] is False
        assert record["runtime_transition_authorized"] is False
        if not pixels.any():
            assert record["presence"] is None
            assert all(g["reason"] == "contrast_unavailable" for g in record["groups"])


def test_profile_missing_roi_is_unknown_not_absence(tmp_path):
    path, layout, frame = _profile(tmp_path)
    profile = HudTemplateProfile.load(path)
    missing = HudLayout("1.0", True, (120, 40), {})
    records = {}
    assert profile.detect_signals(frame, missing, semantic_diagnostics=records) == (
        profile.detect_signals(frame, missing)
    )
    assert records["buy_phase_template"]["reason"] == "roi_unavailable"
    assert records["buy_phase_template"]["absence_checked"] is False


@pytest.mark.parametrize(
    ("signal", "roi", "support"),
    [
        ("buy_phase_template", "center_phase_banner", 2),
        ("buy_phase_template", "player_hp_armor", 3),
        ("hp_hud_structure", "player_hp_armor", 3),
        ("spectated_player_panel", "spectated_player_panel", 3),
    ],
)
def test_invalid_profile_cannot_fall_back_or_prove_identity(tmp_path, signal, roi, support):
    path, layout, frame = _profile(tmp_path, signal=signal, roi=roi, support=support)
    profile = HudTemplateProfile.load(path)
    assert profile.reader_diagnostics
    assert signal not in profile.detect_signals(frame, layout)


def _phase_signal():
    return {
        "buy_phase_template": True,
        "buy_phase_template_confidence": 0.96,
        "buy_phase_template_matcher": "semantic_text_ncc_v1",
    }


def test_phase_needs_temporal_support_and_loses_context_on_nonmatch():
    tracker = SemanticPhaseContext()
    signals = _phase_signal()
    assert not tracker.advance(0, signals, geometry_valid=True)
    assert not tracker.advance(0.02, signals, geometry_valid=True)
    confirmed = tracker.advance(0.08, signals, geometry_valid=True)
    assert confirmed["semantic_buy_phase_confirmed"] is True
    assert confirmed["semantic_buy_phase_source_pts"] == [0, 0.08]
    assert not tracker.advance(0.1, {}, geometry_valid=True)
    assert not tracker.advance(0.2, signals, geometry_valid=True)


@pytest.mark.parametrize("interruption", ["duplicate", "gap", "cut", "geometry"])
def test_phase_cannot_carry_context_across_interruptions(interruption):
    tracker = SemanticPhaseContext()
    signals = _phase_signal()
    tracker.advance(0, signals, geometry_valid=True)
    assert tracker.advance(0.1, signals, geometry_valid=True)
    timestamp = 0.1 if interruption == "duplicate" else 2 if interruption == "gap" else 0.2
    assert not tracker.advance(
        timestamp,
        {**signals, "content_jump": interruption == "cut"},
        geometry_valid=interruption != "geometry",
    )


@pytest.mark.parametrize("score", [None, True, float("nan"), 0.89])
def test_phase_rejects_weak_or_legacy_evidence(score):
    tracker = SemanticPhaseContext()
    signals = {**_phase_signal(), "buy_phase_template_confidence": score}
    assert not tracker.advance(0, signals, geometry_valid=True)
    assert not tracker.advance(0.1, signals, geometry_valid=True)
    signals = _phase_signal()
    signals.pop("buy_phase_template_matcher")
    assert not tracker.advance(0.2, signals, geometry_valid=True)
    assert not tracker.advance(0.3, signals, geometry_valid=True)
