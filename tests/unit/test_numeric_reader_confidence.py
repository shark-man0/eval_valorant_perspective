"""Explicit numeric confidence gates must strengthen, never bypass, safe readers."""

import json
from types import SimpleNamespace

import numpy as np
import pytest

from valorant_ai_coach.hud.readers import ReaderResult
from valorant_ai_coach.hud.templates import HudTemplateProfile, SegmentedDigitsReader


def reader(spec, confidence=0.88, cross_checked=False):
    fallback = SimpleNamespace(
        read=lambda image, roi: ReaderResult(
            "1:26", confidence, ("tesseract_digits",), cross_checked
        )
    )
    return SegmentedDigitsReader(SimpleNamespace(), spec, fallback=fallback)


def test_default_confidence_policy_preserves_existing_reader_result():
    result = reader({"format": "timer_mmss"}).read(None, np.zeros((3, 3), np.uint8))
    assert result.value == "1:26" and result.confidence == 0.88


@pytest.mark.parametrize("cross_checked", [False, True])
def test_explicit_minimum_rejects_low_confidence_even_with_corroboration(cross_checked):
    result = reader(
        {"format": "timer_mmss", "minimum_confidence": 0.90}, cross_checked=cross_checked
    ).read(None, np.zeros((3, 3), np.uint8))
    assert result.value is None and result.confidence == 0.88
    assert not result.cross_checked
    assert "numeric_reader_below_configured_confidence" in result.sources


def test_confidence_boundary_is_inclusive():
    result = reader({"format": "timer_mmss", "minimum_confidence": 0.90}, confidence=0.90).read(
        None, np.zeros((3, 3), np.uint8)
    )
    assert result.value == "1:26" and result.confidence == 0.90


@pytest.mark.parametrize("minimum", [None, True, "0.9", 0.84, 1.01, float("nan")])
def test_invalid_explicit_minimum_keeps_reader_present_and_blocks_legacy_fallback(
    tmp_path, minimum
):
    path = tmp_path / "hud.templates.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "anchors": {},
                "readers": {
                    "round_timer": {
                        "kind": "digits",
                        "format": "timer_mmss",
                        "minimum_confidence": minimum,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    profile = HudTemplateProfile.load(path)
    configured = profile.build_readers()
    assert profile.reader_diagnostics
    assert "round_timer" in configured
    result = configured["round_timer"].read(None, np.zeros((3, 3), np.uint8))
    assert result.value is None
    assert result.sources == ("configured_reader_unavailable",)
