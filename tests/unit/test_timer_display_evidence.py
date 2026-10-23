"""Offline display grammar must not turn punctuation or phase into a timer."""

from copy import deepcopy

import cv2
import numpy as np
import pytest

from scripts.diagnostics.round_lifecycle_evidence import lifecycle
from scripts.diagnostics.round_transition_evidence import integrate
from scripts.diagnostics.timer_display_evidence import TimerDisplayReader
from tests.unit.test_round_lifecycle_evidence import chain
from tests.unit.test_round_transition_evidence import transition
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
