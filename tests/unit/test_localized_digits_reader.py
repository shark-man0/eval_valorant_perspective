from types import SimpleNamespace

import numpy as np
import pytest

from scripts.diagnostics import localized_digits_reader as subject
from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import HudTemplateProfile


@pytest.fixture
def roi():
    return np.zeros((30, 50), np.uint8)


def adapted(monkeypatch, value, confidence, *, minimum=.90, timer=True, sources=("synthetic",)):
    monkeypatch.setattr(subject, "propose", lambda *_args, **_kwargs: (2, 3, 20, 25))
    delegate = SimpleNamespace(read=lambda *_: ReaderResult(value, confidence, sources, True))
    return subject.LocalizedDigitsReader(delegate, timer=timer, minimum=minimum)


def test_wrapper_preserves_value_and_confidence_without_fabricating_crosscheck(monkeypatch, roi):
    result = adapted(monkeypatch, "1:40", .97).read(roi, roi)
    assert result.value == "1:40" and result.confidence == .97
    assert result.sources == ("synthetic", "diagnostic_component_rows")
    assert result.cross_checked is False


@pytest.mark.parametrize("value,confidence", [("1714", .99), ("0:27.46", .99),
    ("1:60", .99), ("1:40", .899), ("1:40", float("nan")), ("1:40", 1.1), ("1:40", True)])
def test_no_format_or_confidence_repair(monkeypatch, roi, value, confidence):
    assert adapted(monkeypatch, value, confidence).read(roi, roi).value is None


def test_stricter_existing_floor_survives_and_empty_provenance_is_rejected(monkeypatch, roi):
    assert adapted(monkeypatch, "1:40", .94, minimum=.95).read(roi, roi).value is None
    assert adapted(monkeypatch, "1:40", .99, sources=()).read(roi, roi).value is None


def test_unlocalized_crop_never_invokes_ocr(monkeypatch, roi):
    monkeypatch.setattr(subject, "propose", lambda *_args, **_kwargs: None)
    delegate = SimpleNamespace(read=lambda *_: pytest.fail("no region, no OCR"))
    result = subject.LocalizedDigitsReader(delegate, timer=True, minimum=.90).read(roi, roi)
    assert result.value is None and result.cross_checked is False


def specs():
    return {name: {"kind": "digits", "templates": {}, "minimum_confidence": .95,
                   "format": "timer_mmss" if name == "round_timer" else "integer"}
            for name in ("round_timer", "ally_score", "enemy_score")}


def test_only_explicit_empty_template_proposals_can_be_injected(tmp_path):
    profile = HudTemplateProfile(tmp_path / "profile.json", {
        "schema_version": "1.0", "readers": specs()})
    readers = subject.build_readers(profile)
    assert all(r.minimum == .95 for r in readers.values())
    assert profile.raw["readers"] == specs()


@pytest.mark.parametrize("change", [
    {"kind": "strict_timer_glyphs"}, {"templates": {"1": "not-present.png"}},
    {"subregion_norm": [0, 0, 1, 1]}, {"minimum_confidence": .85}, {"minimum_confidence": True},
])
def test_no_override_of_strict_reader_assets_or_floor(tmp_path, change):
    raw = specs()
    raw["round_timer"].update(change)
    profile = HudTemplateProfile(tmp_path / "profile.json", {
        "schema_version": "1.0", "readers": raw})
    with pytest.raises(ValueError):
        subject.build_readers(profile)
