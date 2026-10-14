import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from scripts.diagnostics.numeric_text_localization import propose as frozen_propose
from valorant_ai_coach.hud import numeric_regions as subject
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import (
    HudTemplateProfile,
    SegmentedDigitsReader,
    UnavailableConfiguredReader,
)


def clock():
    gray = np.full((85, 125), 35, np.uint8)
    for x, w in ((25, 8), (48, 16), (71, 15)):
        cv2.rectangle(gray, (x, 28), (x + w - 1, 55), 240, -1)
    for y in (35, 47):
        cv2.rectangle(gray, (38, y), (41, y + 3), 240, -1)
    return gray


@pytest.mark.parametrize("timer", [False, True])
def test_proposals_match_frozen_kernel_without_mutating_pixels(timer):
    images = [clock(), np.zeros((85, 125), np.uint8)]
    for seed in range(12):
        images.append(np.random.default_rng(seed).integers(0, 255, (85, 125), np.uint8))
    for image in images:
        before = image.copy()
        assert subject.propose(image, timer=timer) == frozen_propose(image, timer=timer)
        assert np.array_equal(image, before)


def test_no_colon_no_delegate_and_no_value_synthesis():
    image = clock()
    image[:, 38:42] = 35
    reader = subject.LocalizedNumericReader(
        SimpleNamespace(read=lambda *_: pytest.fail("unlocalized text must not invoke OCR")),
        timer=True, minimum=.90)
    assert reader.read(image, image).value is None


@pytest.mark.parametrize("value,confidence,sources,expected", [
    ("1:40", .97, ("synthetic",), "1:40"),
    ("1:40", .94, ("synthetic",), None),
    ("1:60", .99, ("synthetic",), None),
    ("1714", .99, ("synthetic",), None),
    ("0:27.46", .99, ("synthetic",), None),
    ("1:40", float("nan"), ("synthetic",), None),
    ("1:40", True, ("synthetic",), None),
    ("1:40", .99, (), None),
])
def test_value_confidence_and_provenance_are_not_repaired(value, confidence, sources, expected):
    image = clock()
    reader = subject.LocalizedNumericReader(
        SimpleNamespace(read=lambda *_: ReaderResult(value, confidence, sources, True)),
        timer=True, minimum=.95)
    result = reader.read(image, cv2.cvtColor(image, cv2.COLOR_GRAY2BGR))
    assert result.value == expected
    assert result.cross_checked is False
    if expected is not None:
        assert result.confidence == confidence
        assert result.sources == (*sources, subject.LOCATOR)


def profile(tmp_path, spec, roi="round_timer"):
    return HudTemplateProfile(tmp_path / "profile.json", {
        "schema_version": "1.0", "readers": {roi: spec}, "ocr_fallback_rois": []})


def spec():
    return {"kind": "digits", "templates": {}, "format": "timer_mmss",
            "minimum_confidence": .95, "numeric_region_locator": subject.LOCATOR}


def test_native_factory_is_explicit_opt_in_and_preserves_configured_floor(tmp_path):
    raw = spec()
    configured = profile(tmp_path, raw)
    reader = configured.build_readers()["round_timer"]
    assert isinstance(reader, subject.LocalizedNumericReader)
    assert isinstance(reader.delegate, SegmentedDigitsReader)
    assert reader.minimum == reader.delegate.minimum_confidence == .95
    assert configured.raw["readers"]["round_timer"] == raw
    legacy = dict(raw)
    del legacy["numeric_region_locator"]
    assert isinstance(profile(tmp_path, legacy).build_readers()["round_timer"],
                      SegmentedDigitsReader)
    layout = tmp_path / "layout.json"
    layout.write_text("{}", encoding="utf-8")
    configured.path.write_text(json.dumps(configured.raw), encoding="utf-8")
    before = configured.fingerprint(layout)
    configured.path.write_text(json.dumps(profile(tmp_path, legacy).raw), encoding="utf-8")
    assert before != configured.fingerprint(layout)


@pytest.mark.parametrize("change,roi", [
    ({"numeric_region_locator": "unknown"}, "round_timer"),
    ({"kind": "text"}, "round_timer"),
    ({"kind": "strict_timer_glyphs"}, "round_timer"),
    ({"templates": {"1": "missing.png"}}, "round_timer"),
    ({"subregion_norm": [0, 0, 1, 1]}, "round_timer"),
    ({"format": "integer"}, "round_timer"),
    ({"minimum_confidence": .89}, "round_timer"),
    ({"minimum_confidence": True}, "round_timer"),
    ({}, "hp_armor"),
])
def test_invalid_explicit_configuration_cannot_fall_back(tmp_path, change, roi):
    raw = spec()
    raw.update(change)
    configured = profile(tmp_path, raw, roi)
    reader = configured.build_readers()[roi]
    assert isinstance(reader, UnavailableConfiguredReader)
    assert configured.reader_diagnostics
    assert reader.read(clock(), clock()).value is None
