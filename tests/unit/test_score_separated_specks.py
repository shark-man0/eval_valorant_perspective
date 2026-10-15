"""Opt-in interior cleanup: source qualification remains a separate gate."""

import cv2
import numpy as np
import pytest

from tests.unit.test_score_border_specks import centered, glyph
from tests.unit.test_timer_glyphs import _profile, _save_profile_assets, _templates
from valorant_ai_coach.hud.score_glyphs import (
    StrictScoreGlyphReader,
    _remove_isolated_border_specks,
)

MODE = "white200_rowcontrast_separated_specks_v1"
OLD_MODE = "white200_rowcontrast_border_specks_v1"


def reader(mode=MODE):
    return StrictScoreGlyphReader(
        _templates(), comparison_preprocessing="gaussian3x3_v1", foreground_preprocessing=mode
    )


@pytest.mark.parametrize("above", [False, True])
def test_interior_cleanup_requires_explicit_mode_and_preserves_input(above):
    clean = glyph()
    noisy = clean.copy()
    y = 8 if above else 90
    noisy[y : y + 2, 5:7] = 255
    saved = noisy.copy()
    assert np.array_equal(_remove_isolated_border_specks(noisy), saved)
    assert np.array_equal(_remove_isolated_border_specks(noisy, include_interior=True), clean)
    assert np.array_equal(noisy, saved)


@pytest.mark.parametrize(
    "text", ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "99"]
)
def test_current_glyph_evidence_preserves_clean_value_confidence_and_competitors(text):
    clean = centered(text)
    noisy = clean.copy()
    noisy[-6:-4, 2:4] = 255
    baseline = reader(OLD_MODE).read(clean, clean)
    actual = reader().read(noisy, noisy)
    assert (actual.value, actual.confidence) == (baseline.value, baseline.confidence)
    assert actual.value is None or actual.value == text
    assert set(reader().templates) == set("0123456789")
    if actual.value is not None:
        assert actual.sources[-1] == f"foreground_{MODE}"
        assert not actual.cross_checked


@pytest.mark.parametrize(
    "case", ["same_band", "large", "connected", "clipped_core", "clipped_neighbor", "off_center"]
)
def test_ambiguous_structure_cannot_be_removed_as_interior_noise(case):
    a = glyph()
    if case == "same_band":
        a[45:48, 5:7] = 255
    elif case == "large":
        a[80:98, 4:24] = 255
    elif case == "connected":
        a[68:98, 40:42] = 255
    elif case == "clipped_core":
        a[0:31, 38:42] = 255
    elif case == "clipped_neighbor":
        a[30:70, 0:3] = 255
    else:
        a = np.roll(a, 15, axis=1)
        a[90:92, 5:7] = 255
    saved = a.copy()
    assert np.array_equal(_remove_isolated_border_specks(a, include_interior=True), saved)


@pytest.mark.parametrize("text", ["17", "71", "12", "99"])
def test_missing_leading_digit_cannot_be_replaced_by_internal_fragment(text):
    a = centered(text)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(a, 8)
    parts = sorted([(i, *map(int, stats[i])) for i in range(1, count)], key=lambda p: p[1])
    assert len(parts) == 2
    index, x, _, width, _, _ = parts[0]
    a[labels == index] = 0
    a[-6:-4, x : x + min(width, 2)] = 255
    assert reader().read(a, a).value is None


@pytest.mark.parametrize("case", ["blank", "bright", "in_band_dot", "three_digits", "leading_zero"])
def test_full_reader_retains_score_grammar_and_invalid_roi_rejection(case):
    a = centered("7")
    if case == "blank":
        a[:] = 0
    elif case == "bright":
        a[:] = 225
    elif case == "in_band_dot":
        a[35:38, 60:63] = 255
    elif case == "three_digits":
        a = centered("123")
    else:
        a = centered("01")
    assert reader().read(a, a).value is None


def test_mode_requires_gaussian_and_does_not_change_default():
    with pytest.raises(ValueError, match="requires gaussian"):
        StrictScoreGlyphReader(_templates(), foreground_preprocessing=MODE)
    assert StrictScoreGlyphReader(_templates()).foreground_preprocessing == "otsu_v1"


@pytest.mark.parametrize("role", ["ally_score", "enemy_score"])
def test_profile_mode_changes_fingerprint_and_routes_only_explicit_reader(tmp_path, role):
    assets = _save_profile_assets(tmp_path)
    options = {
        "kind": "strict_score_glyphs",
        "templates": assets,
        "comparison_preprocessing": "gaussian3x3_v1",
        "subregion_norm": [0, 0, 1, 1],
    }
    layout = tmp_path / "layout.json"
    layout.write_text("{}", encoding="utf-8")
    old = _profile(tmp_path, roi_name=role, **options, foreground_preprocessing=OLD_MODE)
    before = old.fingerprint(layout)
    new = _profile(tmp_path, roi_name=role, **options, foreground_preprocessing=MODE)
    assert not new.reader_diagnostics
    assert new.build_readers()[role].reader.foreground_preprocessing == MODE
    assert new.fingerprint(layout) != before
