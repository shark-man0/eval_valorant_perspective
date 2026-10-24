"""Offline display grammar must not turn punctuation or phase into a timer."""

from copy import deepcopy

import cv2
import numpy as np
import pytest

from scripts.diagnostics.round_lifecycle_evidence import lifecycle
from scripts.diagnostics.round_transition_evidence import integrate
from scripts.diagnostics.timer_display_evidence import TimerDisplayReader
from tests.hud_evidence_fixtures import chain, transition
from tests.unit.test_timer_glyphs import _render_timer, _templates
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.timer_glyphs import StrictTimerGlyphReader


def decimal(text="29.04", fault=None):
    field = np.zeros((85, 160), np.uint8)
    refs = _templates()
    for digit, x in zip(text.replace(".", ""), (25, 48, 83, 106), strict=True):
        glyph = refs[digit][0]
        field[30:62, x : x + 24] = glyph
    cv2.rectangle(field, (76, 55), (78, 58), 255, -1)
    if fault == "colon":
        cv2.rectangle(field, (76, 43), (78, 46), 255, -1)
    if fault == "missing_dot":
        field[55:59, 76:79] = 0
    if fault == "high_dot":
        field[55:59, 76:79] = 0
        field[33:37, 76:79] = 255
    if fault == "extra_dot":
        field[55:59, 135:138] = 255
    if fault == "clip":
        field[:, 0:30] = 0
        field[:, 0:5] = 255
    return field


class LiteralOcr:
    def __init__(self, value="29.04", confidence=0.96):
        self.value, self.confidence = value, confidence

    def read(self, image, roi):
        return ReaderResult(self.value, self.confidence, ("test_ocr",))


def reader(ocr=True):
    return TimerDisplayReader(
        StrictTimerGlyphReader(_templates(), comparison_preprocessing="gaussian3x3_v1"),
        decimal_reader=LiteralOcr() if ocr else None,
    )


def test_decimal_is_literal_current_display_not_a_colon_or_internal_time():
    im = decimal()
    v = reader().read(im, im)
    assert v.value == "29.04" and v.confidence >= 0.90
    assert "offline_timer_seconds_hundredths_v1" in v.sources


def test_colon_success_is_exactly_preserved():
    im = _render_timer("1:20")
    base = reader().reader.read(im, im)
    v = reader().read(im, im)
    assert (v.value, v.confidence) == (base.value, base.confidence)


@pytest.mark.parametrize(
    "value,confidence",
    [
        ("2904", 0.99),
        ("29:04", 0.99),
        ("29.04", 0.89),
        ("29.04", float("nan")),
        ("29.04", True),
        (None, 0.99),
    ],
)
def test_topology_cannot_authorize_bad_ocr(value, confidence):
    r = reader()
    r.decimal_reader = LiteralOcr(value, confidence)
    im = decimal()
    assert r.read(im, im).value is None


def test_all_digit_classes_remain_competitors_in_glyph_method():
    r = reader(ocr=False)
    assert set(r.digit_reader.templates) == set("0123456789")
    assert r.digit_reader.THRESHOLD == 0.90 and r.digit_reader.CLASS_MARGIN == 0.04


@pytest.mark.parametrize("fault", ["missing_dot", "high_dot", "extra_dot", "clip"])
def test_partial_or_unknown_punctuation_remains_unread(fault):
    im = decimal(fault=fault)
    assert reader().read(im, im).value is None


def test_typed_decimal_can_support_end_but_never_purchase_or_next_clock():
    rows = transition()
    for f in rows:
        f["timer"] = {
            "value": "29.04",
            "confidence": 0.96,
            "sources": ["offline_timer_seconds_hundredths_v1"],
        }
    result = integrate(rows)["candidates"][0]
    assert result["status"] == "DEVELOPMENT_TRANSITION_CANDIDATE"
    assert result["timer_observation_formats"] == ["SECONDS_HUNDREDTHS"]
    assert result["internal_End_tick"] is None
    rows = chain()
    for f in rows:
        if f.get("buy_phase"):
            f["timer"] = {
                "value": "29.04",
                "confidence": 0.96,
                "sources": ["offline_timer_seconds_hundredths_v1"],
            }
    assert lifecycle(rows)["chains"][0]["status"] == "UNKNOWN"


def test_untyped_decimal_or_unobservable_geometry_cannot_clear_unknown():
    for typed in [False, True]:
        rows = transition()
        for f in rows:
            f["timer"] = {
                "value": "29.04",
                "confidence": 0.96,
                "sources": ["offline_timer_seconds_hundredths_v1"] if typed else [],
            }
            if typed:
                f["geometry_consistent"] = False
        assert "timer_unknown" in integrate(rows)["candidates"][0]["reasons"]


def test_decimal_increase_and_frozen_to_colon_switch_remain_explicit():
    rows = transition()
    for f in rows:
        f["timer"] = {
            "value": "29.04",
            "confidence": 0.96,
            "sources": ["offline_timer_seconds_hundredths_v1"],
        }
    before = deepcopy(rows)
    rows[5]["timer"]["value"] = "29.06"
    assert "timer_contradiction" in integrate(rows)["candidates"][0]["reasons"]
    rows = before
    rows[5]["timer"] = {"value": "0:06", "confidence": 0.96}
    c = integrate(rows)["candidates"][0]
    assert c["timer_format_changes"] and c["formal_events"] == []


def test_one_read_per_format_does_not_establish_consistent_timer():
    rows = transition()
    for f in rows:
        f["timer"]["value"] = None
    rows[3]["timer"] = {
        "value": "29.04",
        "confidence": 0.96,
        "sources": ["offline_timer_seconds_hundredths_v1"],
    }
    rows[5]["timer"] = {"value": "0:06", "confidence": 0.96}
    c = integrate(rows)["candidates"][0]
    assert c["timer_status"] == "UNKNOWN" and "timer_unknown" in c["reasons"]


def test_decimal_reset_across_score_is_a_contradiction():
    rows = transition()
    for f in rows:
        f["timer"] = {
            "value": "29.04" if f["tick"] < 2 else "30.04",
            "confidence": 0.96,
            "sources": ["offline_timer_seconds_hundredths_v1"],
        }
    assert "timer_reset_at_score_boundary" in integrate(rows)["candidates"][0]["reasons"]


def test_a_geometry_receipt_does_not_make_blank_timer_pixels_readable():
    from tests.unit.test_round_component_geometry import bound_rows

    rows, image, *_ = bound_rows()
    assert rows[0]["component_geometry"]["roles"]["timer"]
    empty = np.zeros((85, 125, 3), np.uint8)
    assert reader().read(image, empty).value is None


def test_profile_timer_extension_preserves_configured_inner_roi_and_accepted_read():
    from scripts.diagnostics.timer_display_evidence import ProfileTimerDisplayReader
    from valorant_ai_coach.hud.templates import SubregionReader
    glyph = _render_timer('1:20')
    height, width = glyph.shape
    outer = np.full((height+40, width+40), 110, np.uint8)
    outer[20:height+20, 20:width+20] = glyph
    bounds = (20/(width+40), 20/(height+40), (width+20)/(width+40), (height+20)/(height+40))
    strict = StrictTimerGlyphReader(_templates(), comparison_preprocessing='gaussian3x3_v1')
    baseline = SubregionReader(strict, bounds)
    expected = baseline.read(outer, outer)
    assert expected.value == '1:20'
    extended = ProfileTimerDisplayReader(baseline, decimal_reader=LiteralOcr())
    assert extended.baseline is baseline and baseline.bounds == bounds
    assert extended.read(outer, outer) == expected


def test_profile_timer_extension_does_not_convert_an_unobserved_colon():
    from scripts.diagnostics.timer_display_evidence import ProfileTimerDisplayReader
    strict = StrictTimerGlyphReader(_templates(), comparison_preprocessing='gaussian3x3_v1')
    extended = ProfileTimerDisplayReader(strict, decimal_reader=LiteralOcr('29:04'))
    assert extended.read(decimal(), decimal()).value is None


def test_explicit_native_timer_foreground_recovers_background_without_grammar_changes():
    from scripts.diagnostics.timer_display_evidence import ProfileTimerDisplayReader
    field = cv2.copyMakeBorder(_render_timer('1:20'),8,8,8,8,cv2.BORDER_CONSTANT,value=0)
    background = np.repeat(np.linspace(120,230,field.shape[0],dtype=np.uint8)[:,None],
                           field.shape[1],axis=1)
    image = np.where(field > 0,field,background).astype(np.uint8)
    original = image.copy()
    strict = StrictTimerGlyphReader(_templates(),comparison_preprocessing='gaussian3x3_v1')
    baseline = ProfileTimerDisplayReader(strict)
    assert baseline.read(image,image).value is None
    alternative = ProfileTimerDisplayReader(
        strict,foreground_preprocessing='native_white200_rowcontrast_v1')
    actual = alternative.read(image,image)
    assert actual.value == '1:20' and actual.confidence >= .90
    assert 'offline_timer_native_rowcontrast_v1' in actual.sources
    assert strict.THRESHOLD == .90 and strict.CLASS_MARGIN == .04
    np.testing.assert_array_equal(image,original)


def test_native_timer_foreground_preserves_success_and_rejects_missing_punctuation():
    from scripts.diagnostics.timer_display_evidence import ProfileTimerDisplayReader
    strict = StrictTimerGlyphReader(_templates(),comparison_preprocessing='gaussian3x3_v1')
    alternative = ProfileTimerDisplayReader(
        strict,foreground_preprocessing='native_white200_rowcontrast_v1')
    image = _render_timer('1:20')
    assert alternative.read(image,image) == strict.read(image,image)
    assert alternative.read(decimal(),decimal()).value is None
    for value in (0,120,255):
        blank = np.full_like(image,value)
        assert alternative.read(blank,blank).value is None
    with pytest.raises(ValueError,match='foreground'):
        ProfileTimerDisplayReader(strict,foreground_preprocessing='white199')


def test_native_timer_foreground_uses_the_profile_inner_roi_and_keeps_outer_pixels():
    from scripts.diagnostics.timer_display_evidence import ProfileTimerDisplayReader
    from valorant_ai_coach.hud.templates import SubregionReader
    field = cv2.copyMakeBorder(_render_timer('1:20'),8,8,8,8,cv2.BORDER_CONSTANT,value=0)
    bg = np.repeat(np.linspace(120,230,field.shape[0],dtype=np.uint8)[:,None],
                   field.shape[1],axis=1)
    field = np.where(field>0,field,bg).astype(np.uint8)
    h,w = field.shape
    outer = np.full((h+20,w+40),255,np.uint8)
    outer[10:10+h,20:20+w] = field
    original = outer.copy()
    strict = StrictTimerGlyphReader(_templates(),comparison_preprocessing='gaussian3x3_v1')
    bounds = (20/(w+40),10/(h+20),(20+w)/(w+40),(10+h)/(h+20))
    parent = SubregionReader(strict,bounds)
    observed = ProfileTimerDisplayReader(
        parent,foreground_preprocessing='native_white200_rowcontrast_v1').read(outer,outer)
    assert observed.value == '1:20'
    assert parent.bounds == bounds
    np.testing.assert_array_equal(outer,original)


def test_complete_colon_band_keeps_glyphs_but_excludes_outside_baseline_noise():
    from scripts.diagnostics.timer_display_evidence import ProfileTimerDisplayReader
    image = cv2.copyMakeBorder(_render_timer('1:20'),8,8,8,8,
                               cv2.BORDER_CONSTANT,value=0)
    image[image.shape[0]-3,60] = 255  # Background below every complete digit.
    before = image.copy()
    strict = StrictTimerGlyphReader(_templates(),comparison_preprocessing='gaussian3x3_v1')
    old = ProfileTimerDisplayReader(
        strict,foreground_preprocessing='native_white200_rowcontrast_v1')
    assert old.read(image,image).value is None
    new = ProfileTimerDisplayReader(
        strict,foreground_preprocessing='native_white200_rowcontrast_band_v2')
    result = new.read(image,image)
    assert result.value == '1:20' and result.confidence >= .90
    assert 'offline_timer_complete_colon_band_v2' in result.sources
    np.testing.assert_array_equal(image,before)


@pytest.mark.parametrize('fault',['dot','double_colon','missing_colon','clip'])
def test_colon_band_cannot_remove_same_baseline_fragments_or_repair_clipping(fault):
    from scripts.diagnostics.timer_display_evidence import ProfileTimerDisplayReader
    image = _render_timer('1:20',extra='' if fault=='clip' else fault,
                          clip_left=fault=='clip')
    strict = StrictTimerGlyphReader(_templates(),comparison_preprocessing='gaussian3x3_v1')
    new = ProfileTimerDisplayReader(
        strict,foreground_preprocessing='native_white200_rowcontrast_band_v2')
    assert new.read(image,image).value is None


def test_colon_band_preserves_existing_success_and_unchanged_strict_competitors():
    from scripts.diagnostics.timer_display_evidence import ProfileTimerDisplayReader
    strict = StrictTimerGlyphReader(_templates(),comparison_preprocessing='gaussian3x3_v1')
    new = ProfileTimerDisplayReader(
        strict,foreground_preprocessing='native_white200_rowcontrast_band_v2')
    image = _render_timer('1:20')
    assert new.read(image,image) == strict.read(image,image)
    assert strict.THRESHOLD == .90 and strict.CLASS_MARGIN == .04
    assert set(strict.templates) == set('0123456789')
