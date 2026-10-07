import json

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.identity import live_identity
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.spectator import panel_components
from valorant_ai_coach.hud.templates import HudTemplateProfile


@pytest.fixture
def variant_profile(tmp_path, panel_images):
    image = panel_images(160, 126)[0]
    reference = panel_components(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY))
    assert reference is not None
    for prefix in ("primary", "variant"):
        for name, array in (("template", reference), ("support_regions", reference.regions),
                            ("orientation", reference.orientation)):
            assert cv2.imwrite(str(tmp_path / f"{prefix}-{name}.png"), array)
    header = np.full((24, 100), 30, np.uint8)
    mask = np.zeros(header.shape, np.uint8)
    regions = np.zeros(header.shape, np.uint8)
    for group, left in enumerate((10, 65), 1):
        mask[4:20, left:left + 22] = 255
        regions[4:20, left:left + 22] = group
        header[4:20, left:left + 22] = np.random.default_rng(group).integers(
            30, 230, (16, 22), dtype=np.uint8
        )
    for name, array in (("template", header), ("mask", mask), ("support_regions", regions)):
        assert cv2.imwrite(str(tmp_path / f"report-{name}.png"), array)
    raw = {"schema_version": "1.0", "report_header_detector": {
        "version": 1, "method": "independent_static_header_v1", "roi": "combat_report",
        "threshold": .90, "template": "report-template.png", "mask": "report-mask.png",
        "support_regions": "report-support_regions.png", "input_shape": [90, 150],
        "reference_x": 20 / 150,
    }, "spectator_panel_detector": {
        "version": 2, "template": "primary-template.png",
        "support_regions": "primary-support_regions.png", "orientation": "primary-orientation.png",
    }, "report_gated_spectator_panel_references": [{
        "version": 2, "method": "oriented_component_regions_v2", "roi": "spectated_player_panel",
        "threshold": .90, "template": "variant-template.png",
        "support_regions": "variant-support_regions.png", "orientation": "variant-orientation.png",
    }]}
    path = tmp_path / "profile.json"

    def load():
        path.write_text(json.dumps(raw))
        return HudTemplateProfile.load(path)

    frame = np.full((126, 310, 3), 30, np.uint8)
    frame[:, :160] = image
    frame[17:41, 180:280] = cv2.cvtColor(header, cv2.COLOR_GRAY2BGR)
    layout = HudLayout("1.0", True, (310, 126), {
        "spectated_player_panel": NormalizedRoi(0, 0, 160 / 310, 1),
        "combat_report": NormalizedRoi(160 / 310, 0, 150 / 310, 90 / 126),
    })
    return raw, load, frame, layout


def routing(monkeypatch, profile, *, primary=None, variant=True, confidence=.96):
    calls = []

    def detect(crop, reference):
        is_primary = reference is profile._panel_components
        calls.append("primary" if is_primary else "variant")
        present = primary if is_primary else variant
        return {"checked": present is not None, "panel_present": present,
                "reason": "test_contract", "positive_component_scores": [confidence] * 3}

    monkeypatch.setattr("valorant_ai_coach.hud.templates.detect_panel", detect)
    return calls


def test_independent_report_and_variant_block_player_identity(
    variant_profile, monkeypatch, live_identity_signals
):
    _, load, frame, layout = variant_profile
    profile = load()
    assert not profile.reader_diagnostics
    calls = routing(monkeypatch, profile)
    signals = profile.detect_signals(frame, layout)
    assert calls == ["primary", "variant"]
    assert signals["spectator_detector_checked"] and signals["spectator_panel_present"]
    assert signals["spectator_panel_absent"] is False
    assert not live_identity({**live_identity_signals, **signals}, geometry_valid=True).live


def test_report_must_be_current_and_cannot_come_from_context(variant_profile, monkeypatch):
    _, load, frame, layout = variant_profile
    profile = load()
    calls = routing(monkeypatch, profile)
    assert profile.detect_signals(frame, layout)["spectator_panel_present"]
    frame[:, 160:] = 30
    signals = profile.detect_signals(frame, layout, context={"combat_report_visible": True})
    assert calls == ["primary", "variant", "primary"]
    assert signals["spectator_panel_present"] is None
    assert signals["spectator_detector_checked"] is False
    assert "self_hud_identity_trustworthy" not in signals


@pytest.mark.parametrize("variant", [False, None])
def test_additional_reference_cannot_contribute_absence(variant_profile, monkeypatch, variant):
    _, load, frame, layout = variant_profile
    profile = load()
    routing(monkeypatch, profile, primary=None, variant=variant)
    signals = profile.detect_signals(frame, layout)
    assert signals["spectator_panel_present"] is None
    assert signals["spectator_detector_checked"] is False
    assert signals["spectator_panel_absent"] is False


def test_existing_presence_wins_without_consulting_variant(variant_profile, monkeypatch):
    _, load, frame, layout = variant_profile
    profile = load()
    calls = routing(monkeypatch, profile, primary=True, variant=None)
    assert profile.detect_signals(frame, layout)["spectator_panel_present"]
    assert calls == ["primary"]


def test_configured_stronger_threshold_is_enforced(variant_profile, monkeypatch):
    raw, load, frame, layout = variant_profile
    raw["report_gated_spectator_panel_references"][0]["threshold"] = .99
    profile = load()
    routing(monkeypatch, profile, primary=False, confidence=.96)
    signals = profile.detect_signals(frame, layout)
    assert signals["spectator_panel_present"] is False
    assert signals["spectator_panel_absent"] is True


@pytest.mark.parametrize("threshold", [.89, True, None, float("nan")])
def test_invalid_threshold_diagnoses_and_disables_variant(variant_profile, threshold):
    raw, load, _, _ = variant_profile
    raw["report_gated_spectator_panel_references"][0]["threshold"] = threshold
    profile = load()
    assert not profile._report_gated_panels
    assert any("report_gated_spectator" in s for s in profile.reader_diagnostics)


def test_missing_asset_does_not_load_partial_variant_bank(variant_profile):
    raw, load, _, _ = variant_profile
    broken = {**raw["report_gated_spectator_panel_references"][0], "template": "missing.png"}
    raw["report_gated_spectator_panel_references"].append(broken)
    profile = load()
    assert not profile._report_gated_panels
    assert any("report_gated_spectator" in s for s in profile.reader_diagnostics)


def test_invalid_report_disables_variant(variant_profile):
    raw, load, _, _ = variant_profile
    raw["report_header_detector"]["threshold"] = .89
    profile = load()
    assert not profile._report_gated_panels
    assert any("report_gated_spectator" in s for s in profile.reader_diagnostics)


@pytest.mark.parametrize("value", [None, False, 0, "invalid", {}, [None]])
def test_malformed_variant_bank_is_diagnosed(variant_profile, value):
    raw, load, _, _ = variant_profile
    raw["report_gated_spectator_panel_references"] = value
    profile = load()
    assert not profile._report_gated_panels
    assert any("report_gated_spectator" in s for s in profile.reader_diagnostics)


def test_empty_variant_bank_preserves_legacy_profile(variant_profile):
    raw, load, _, _ = variant_profile
    raw["report_gated_spectator_panel_references"] = []
    profile = load()
    assert not profile._report_gated_panels
    assert not profile.reader_diagnostics


def test_legacy_report_signal_cannot_enable_variant(variant_profile, monkeypatch):
    _, load, frame, layout = variant_profile
    profile = load()
    calls = routing(monkeypatch, profile, primary=False)
    # Simulate the independent detector rejecting a frame even when a legacy
    # pixel template has accepted Report visibility in that same frame.
    monkeypatch.setattr(
        "valorant_ai_coach.hud.templates.report_header_evidence",
        lambda *_: {"present": False, "score": 0.2},
    )
    from valorant_ai_coach.hud.templates import LoadedTemplate

    image = frame[17:41, 180:280, 0].copy()
    profile._signal_templates["combat_report_visible"] = (
        "combat_report", LoadedTemplate("legacy_report", profile.path, image, .90)
    )
    signals = profile.detect_signals(frame, layout)
    assert signals["combat_report_visible"] is True
    assert calls == ["primary"]
    assert signals["spectator_panel_present"] is False
    assert signals["spectator_panel_absent"] is True
