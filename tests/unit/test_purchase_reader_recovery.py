"""Offline recovery retains accepted pixels, Profile crops and digit competitors."""

import json

import numpy as np
import pytest

from scripts.diagnostics.round_transition_evidence import score_readers
from scripts.diagnostics.score_border_background import RejectedScoreBackgroundReader
from tests.unit.test_round_transition_evidence import score_profile
from tests.unit.test_score_glyphs import render
from tests.unit.test_timer_glyphs import _templates
from valorant_ai_coach.hud.score_glyphs import StrictScoreGlyphReader
from valorant_ai_coach.hud.templates import SubregionReader


def test_recovery_is_explicit_and_preserves_profile_crop_and_assets(tmp_path):
    path = score_profile(tmp_path)
    spec = json.loads(path.read_text())
    bounds = [0.2, 0.1, 0.6, 0.9]
    for role in ("ally_score", "enemy_score"):
        spec["readers"][role]["subregion_norm"] = bounds
    path.write_text(json.dumps(spec))
    before = path.read_bytes()
    default, old = score_readers(path, foreground="white200_rowcontrast_v1")
    recovered, new = score_readers(
        path, foreground="white200_rowcontrast_v1", background_fallback=True,
    )
    for role in recovered:
        assert isinstance(recovered[role], SubregionReader)
        assert recovered[role].bounds == default[role].bounds == tuple(bounds)
        assert isinstance(recovered[role].reader, RejectedScoreBackgroundReader)
        assert isinstance(default[role].reader, StrictScoreGlyphReader)
    assert old["asset_sha256"] == new["asset_sha256"]
    assert old["parent_profile_sha256"] == new["parent_profile_sha256"]
    assert "rejected_native_background" not in old
    assert new["rejected_native_background"] is True
    assert path.read_bytes() == before


@pytest.mark.parametrize("flag", [1, "true", None])
def test_recovery_does_not_accept_truthy_configuration(tmp_path, flag):
    with pytest.raises(ValueError, match="boolean"):
        score_readers(score_profile(tmp_path), background_fallback=flag)


@pytest.mark.parametrize("foreground", ["white200_v1", "otsu_v1"])
def test_recovery_requires_frozen_baseline_configuration(foreground):
    base = StrictScoreGlyphReader(
        _templates(), comparison_preprocessing="gaussian3x3_v1",
        foreground_preprocessing=foreground,
    )
    with pytest.raises(ValueError, match="baseline"):
        RejectedScoreBackgroundReader(base)


def test_score_recovery_preserves_success_and_original_thresholds():
    base = StrictScoreGlyphReader(
        _templates(),
        comparison_preprocessing="gaussian3x3_v1",
        foreground_preprocessing="white200_rowcontrast_v1",
    )
    reader = RejectedScoreBackgroundReader(base)
    roi = render("0")
    a = base.read(roi, roi)
    b = reader.read(roi, roi)
    assert a.value is not None and b == a
    assert (
        reader.alternative.reader.THRESHOLD == 0.90
        and reader.alternative.reader.CLASS_MARGIN == 0.04
    )


def test_blank_score_pixels_cannot_be_recovered():
    base = StrictScoreGlyphReader(
        _templates(),
        comparison_preprocessing="gaussian3x3_v1",
        foreground_preprocessing="white200_rowcontrast_v1",
    )
    image = np.full((45, 44), 255, np.uint8)
    assert RejectedScoreBackgroundReader(base).read(image, image).value is None


def test_native_background_removal_recovers_a_known_synthetic_digit():
    # A thin scene row develops interpolation halos when background removal
    # follows enlargement. The digit itself and all competitor assets are fixed.
    roi = render("0")
    roi[10:11] = np.maximum(roi[10:11], 180)
    before = roi.copy()
    base = StrictScoreGlyphReader(
        _templates(), comparison_preprocessing="gaussian3x3_v1",
        foreground_preprocessing="white200_rowcontrast_v1",
    )
    assert base.read(roi, roi).value is None
    recovered = RejectedScoreBackgroundReader(base).read(roi, roi)
    assert recovered.value == "0" and recovered.confidence >= 0.90
    assert "offline_rejected_native_score_background_v1" in recovered.sources
    assert np.array_equal(roi, before)
