import json
from dataclasses import replace

import cv2
import numpy as np
import pytest

from valorant_ai_coach.hud.identity import live_identity
from valorant_ai_coach.hud.layout import HudLayout, NormalizedRoi
from valorant_ai_coach.hud.report_header import ReportHeader, report_header_evidence
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.hud.temporal import _player_death_event


@pytest.fixture
def header():
    rng = np.random.default_rng(17)
    reference = np.full((24, 100), 30, np.uint8)
    mask = np.zeros(reference.shape, np.uint8)
    regions = np.zeros(reference.shape, np.uint8)
    for group, a in enumerate((10, 65), 1):
        mask[4:20, a : a + 22] = 255
        regions[4:20, a : a + 22] = group
        reference[4:20, a : a + 22] = rng.integers(30, 230, (16, 22), dtype=np.uint8)
    model = ReportHeader(reference, mask, regions, (90, 150), 20 / 150, 0.90)
    model.validate()
    image = np.full(model.input_shape, 30, np.uint8)
    image[17:41, 20:120] = reference
    return model, image


def test_static_header_localizes_and_excluded_values_do_not_define_presence(header):
    model, image = header
    assert report_header_evidence(image, model)["present"] is True
    altered = np.random.default_rng(82).integers(0, 256, image.shape, dtype=np.uint8)
    support = np.zeros(image.shape, bool)
    support[17:41, 20:120] = model.mask > 0
    altered[support] = image[support]
    result = report_header_evidence(altered, model)
    assert result["present"] is True
    assert result["score"] == pytest.approx(1.0)


@pytest.mark.parametrize("group", (1, 2))
@pytest.mark.parametrize("alteration", ("erase", "invert", "different_shape"))
def test_each_independent_group_is_required_and_contradictions_reject(header, group, alteration):
    model, image = header
    selected = (model.mask > 0) & (model.regions == group)
    patch = image[17:41, 20:120]
    if alteration == "erase":
        patch[selected] = 30
    elif alteration == "invert":
        patch[selected] = 255 - patch[selected]
    else:
        patch[selected] = np.random.default_rng(28).integers(0, 256, selected.sum(), np.uint8)
    assert report_header_evidence(image, model)["present"] is None


def test_flat_world_texture_and_partial_geometry_cannot_prove_report(header):
    model, image = header
    for negative in (
        np.full(image.shape, 30, np.uint8),
        np.random.default_rng(93).integers(0, 256, image.shape, np.uint8),
        image[:40],
    ):
        assert report_header_evidence(negative, model)["present"] is None


@pytest.mark.parametrize("threshold", (0.89, True, float("nan")))
def test_threshold_cannot_be_weakened(header, threshold):
    model, _ = header
    with pytest.raises(ValueError):
        replace(model, threshold=threshold).validate()


def make_profile(tmp_path, model, **overrides):
    for name, array in (
        ("template", model.reference),
        ("mask", model.mask),
        ("support_regions", model.regions),
    ):
        assert cv2.imwrite(str(tmp_path / f"{name}.png"), array)
    spec = {
        "version": 1,
        "method": "independent_static_header_v1",
        "roi": "combat_report",
        "threshold": 0.90,
        "template": "template.png",
        "mask": "mask.png",
        "support_regions": "support_regions.png",
        "input_shape": list(model.input_shape),
        "reference_x": model.reference_x,
    }
    spec.update(overrides)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({"schema_version": "1.0", "report_header_detector": spec}))
    return HudTemplateProfile.load(path)


def report_layout():
    return HudLayout("1.0", True, (150, 90), {"combat_report": NormalizedRoi(0, 0, 1, 1)})


def test_profile_only_adds_report_and_cannot_clear_legacy_positive(tmp_path, header):
    model, image = header
    profile = make_profile(tmp_path, model)
    positive = profile.detect_signals(image, report_layout())
    assert positive["combat_report_visible"] is True
    assert positive["combat_report_confidence"] >= 0.90
    negative = profile.detect_signals(np.full(image.shape, 30, np.uint8), report_layout())
    assert "combat_report_visible" not in negative
    assert {"combat_report_visible": True, **negative}["combat_report_visible"] is True
    assert {"template.png", "mask.png", "support_regions.png"} <= {
        p.name for p in profile.asset_paths
    }


@pytest.mark.parametrize(
    "overrides",
    (
        {"roi": "abilities"},
        {"method": "value_invariant_edges_v1"},
        {"threshold": 0.89},
        {"expected_state": "report"},
        {"timestamp": 1},
        {"input_shape": [True, 150]},
    ),
)
def test_invalid_role_or_oracle_contract_never_activates(tmp_path, header, overrides):
    model, image = header
    profile = make_profile(tmp_path, model, **overrides)
    assert any("report_header_detector" in s for s in profile.reader_diagnostics)
    assert "combat_report_visible" not in profile.detect_signals(image, report_layout())


def test_report_blocks_live_without_supplying_death_or_missing_identity_evidence(
    header,
    live_identity_signals,
):
    model, image = header
    result = report_header_evidence(image, model)
    signals = {**live_identity_signals, "combat_report_visible": result["present"]}
    assert not live_identity(signals, geometry_valid=True).live
    assert "self_hud_identity_lost" not in result
    assert _player_death_event(0, 0.95, {"combat_report_visible": True}, {}) is None
