"""Partial clock evidence cannot relax the full parser or invent exact seconds."""

from types import SimpleNamespace

import cv2
import pytest
from test_timer_glyphs import _reader, _render_timer, _templates

from valorant_ai_coach.hud.templates import SubregionReader
from valorant_ai_coach.temporal.clock_components import clock_components
from valorant_ai_coach.temporal.match_observer import ProfileHudObserver


def test_unread_seconds_keep_numeric_clock_unknown_but_preserve_minute():
    templates = _templates()
    templates["8"] = [templates["9"][0].copy()]
    reader = _reader(templates)
    image = _render_timer("1:39")
    assert reader.read(image, image).value is None
    value = clock_components(image, reader)
    assert value["minute"] == 1
    assert value["active_prefix_supported"] is True
    assert value["components"][-1]["accepted"] is False
    assert all(len(v["all_ten_class_scores"]) == 10 for v in value["components"])
    assert value["threshold"] == 0.90 and value["class_margin"] == 0.04
    assert value["numeric_clock_imputed"] is value["qualified"] is False


def test_ambiguous_minute_does_not_support_phase():
    templates = _templates()
    templates["4"] = [templates["1"][0].copy()]
    image = _render_timer("1:39")
    value = clock_components(image, _reader(templates))
    assert value["minute"] is None and value["active_prefix_supported"] is False


@pytest.mark.parametrize("text", ["0:39", "1:99"])
def test_zero_minute_or_confident_invalid_seconds_cannot_support_active(text):
    value = clock_components(_render_timer(text), _reader())
    assert value["active_prefix_supported"] is False


@pytest.mark.parametrize("extra", ["missing_colon", "double_colon", "slash", "dot"])
def test_partial_evidence_keeps_the_original_structural_rejections(extra):
    value = clock_components(_render_timer("1:39", extra=extra), _reader())
    assert value["minute"] is None and value["active_prefix_supported"] is False


def test_clipped_clock_cannot_authorize_partial_phase():
    value = clock_components(_render_timer("1:39", clip_left=True), _reader())
    assert value["active_prefix_supported"] is False


@pytest.mark.parametrize(
    ("enabled", "structure", "ui", "expected"),
    [
        (True, True, {}, ["active"]),
        (False, True, {}, []),
        (True, False, {}, []),
        (True, True, {"buy_phase_template": True}, ["buy"]),
        (True, True, {"round_end_template": True}, ["result"]),
    ],
)
def test_opt_in_partial_clock_respects_geometry_buy_and_result(enabled, structure, ui, expected):
    templates = _templates()
    templates["8"] = [templates["9"][0].copy()]
    observer = ProfileHudObserver.__new__(ProfileHudObserver)
    observer.clock_prefix = enabled
    observer.bindings = {"profile": "synthetic"}
    observer.layout = SimpleNamespace(
        regions={"round_timer": None},
        normalized_roi=lambda _: SimpleNamespace(pixel_bounds=lambda w, h: (0, 0, w, h)),
        validate_calibration=lambda *a, **kw: SimpleNamespace(calibrated=structure, reasons=[]),
    )
    observer.profile = SimpleNamespace(
        detect_anchors=lambda *a: ({}, {}, []), detect_signals=lambda *a, **kw: ui
    )
    observer.round_scope = None
    observer.analyzer = SimpleNamespace(
        readers={"round_timer": SubregionReader(_reader(templates), (0.0, 0.0, 1.0, 1.0))}
    )
    image = cv2.cvtColor(_render_timer("1:39"), cv2.COLOR_GRAY2BGR)
    value = observer.inspect(image)
    assert value["signals"] == expected
    assert value["raw"]["values"]["round_timer"]["value"] is None
    assert value["context"]["timer_seconds"] is None
