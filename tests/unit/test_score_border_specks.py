"""Synthetic mask safety controls, not source qualification."""

import cv2
import numpy as np
import pytest

from tests.unit.test_score_glyphs import render
from tests.unit.test_timer_glyphs import _templates
from valorant_ai_coach.hud.score_glyphs import (
    StrictScoreGlyphReader,
    _remove_isolated_border_specks,
)

MODE = "white200_rowcontrast_border_specks_v1"


def candidate_reader():
    return StrictScoreGlyphReader(
        _templates(), comparison_preprocessing="gaussian3x3_v1", foreground_preprocessing=MODE
    )


def glyph():
    a = np.zeros((100, 100), np.uint8)
    a[30:70, 38:42] = 255
    a[30:34, 38:62] = 255
    a[66:70, 38:62] = 255
    a[30:70, 58:62] = 255
    return a


def test_complete_centered_glyph_retained_and_separate_bottom_speck_removed():
    a = glyph()
    base = a.copy()
    a[98:100, 5:7] = 255
    original = a.copy()
    assert np.array_equal(_remove_isolated_border_specks(a), base)
    assert np.array_equal(a, original)


@pytest.mark.parametrize(
    "case",
    [
        "same_band",
        "large",
        "connected",
        "clipped_core",
        "clipped_neighbor",
        "off_center",
        "internal",
        "blank",
    ],
)
def test_uncertain_or_clipped_information_is_preserved_for_existing_rejection(case):
    a = glyph()
    if case == "same_band":
        a[45:48, 0:2] = 255
    elif case == "large":
        a[85:100, 0:20] = 255
    elif case == "connected":
        a[68:100, 40:42] = 255
    elif case == "clipped_core":
        a[0:31, 38:42] = 255
    elif case == "clipped_neighbor":
        a[30:70, 0:3] = 255
    elif case == "off_center":
        a = np.roll(a, 15, axis=1)
        a[99, 0] = 255
    elif case == "internal":
        a[90:92, 5:7] = 255
    else:
        a[:] = 0
    assert np.array_equal(_remove_isolated_border_specks(a), a)


def test_two_complete_centered_digits_are_never_collapsed_to_one():
    a = np.zeros((100, 100), np.uint8)
    a[30:70, 25:35] = 255
    a[30:70, 65:75] = 255
    base = a.copy()
    a[99, 0] = 255
    result = _remove_isolated_border_specks(a)
    assert np.array_equal(result, base)


def centered(text):
    a = render(text)
    x, y, w, h = cv2.boundingRect(cv2.findNonZero(a))
    out = np.zeros_like(a)
    left = (out.shape[1] - w) // 2
    out[y : y + h, left : left + w] = a[y : y + h, x : x + w]
    return out


@pytest.mark.parametrize(
    "text", ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "12", "99"]
)
def test_border_cleanup_preserves_clean_baseline_and_all_digit_competitors(text):
    a = centered(text)
    clean = a.copy()
    a[-1, 0] = 255
    old = StrictScoreGlyphReader(
        _templates(),
        comparison_preprocessing="gaussian3x3_v1",
        foreground_preprocessing="white200_rowcontrast_v1",
    ).read(a, a)
    new = candidate_reader().read(a, a)
    assert old.value is None
    baseline = StrictScoreGlyphReader(
        _templates(),
        comparison_preprocessing="gaussian3x3_v1",
        foreground_preprocessing="white200_rowcontrast_v1",
    ).read(clean, clean)
    assert (new.value, new.confidence) == (baseline.value, baseline.confidence)
    assert new.value is None or new.value == text
    assert set(candidate_reader().templates) == set("0123456789")


@pytest.mark.parametrize("text", ["17", "71", "12", "99"])
def test_partial_leading_digit_below_baseline_is_not_dropped_as_noise(text):
    a = centered(text)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(a, 8)
    parts = sorted([(i, *map(int, stats[i])) for i in range(1, n)], key=lambda p: p[1])
    assert len(parts) == 2
    first = parts[0]
    i, x, y, w, h, area = first
    a[labels == i] = 0
    a[-1, x : x + min(w, 2)] = 255
    assert candidate_reader().read(a, a).value is None


@pytest.mark.parametrize(
    "case",
    [
        "blank",
        "bright",
        "internal_dot",
        "same_band_border",
        "clipped",
        "three_digits",
        "leading_zero",
    ],
)
def test_full_reader_preserves_invalid_structure_controls(case):
    a = centered("7")
    if case == "blank":
        a[:] = 0
    elif case == "bright":
        a[:] = 225
    elif case == "internal_dot":
        a[35:38, 60:63] = 255
    elif case == "same_band_border":
        a[20:23, 0:2] = 255
    elif case == "clipped":
        x, y, w, h = cv2.boundingRect(cv2.findNonZero(a))
        a = a[:, x + 2 :]
    elif case == "three_digits":
        a = render("123")
    else:
        a = centered("01")
    assert candidate_reader().read(a, a).value is None


def test_mode_is_explicit_and_requires_frozen_gaussian_comparison():
    with pytest.raises(ValueError, match="requires gaussian"):
        StrictScoreGlyphReader(_templates(), foreground_preprocessing=MODE)
    assert StrictScoreGlyphReader(_templates()).foreground_preprocessing == "otsu_v1"
    source = centered("7")
    source[-1, 0] = 255
    result = candidate_reader().read(source, source)
    assert result.value == "7"
    assert result.sources[-1] == f"foreground_{MODE}"
    assert result.cross_checked is False


@pytest.mark.parametrize("role", ["ally_score", "enemy_score"])
def test_profile_routes_explicit_mode_and_binds_it_in_fingerprint(tmp_path, role):
    from tests.unit.test_timer_glyphs import _profile, _save_profile_assets

    assets = _save_profile_assets(tmp_path)
    options = {
        "kind": "strict_score_glyphs",
        "templates": assets,
        "comparison_preprocessing": "gaussian3x3_v1",
        "subregion_norm": [0, 0, 1, 1],
    }
    layout = tmp_path / "layout.json"
    layout.write_text("{}", encoding="utf-8")
    old = _profile(
        tmp_path, roi_name=role, **options, foreground_preprocessing="white200_rowcontrast_v1"
    )
    before = old.fingerprint(layout)
    new = _profile(tmp_path, roi_name=role, **options, foreground_preprocessing=MODE)
    assert not new.reader_diagnostics
    assert new.build_readers()[role].reader.foreground_preprocessing == MODE
    assert new.fingerprint(layout) != before
