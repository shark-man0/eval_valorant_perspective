import copy
import json

import cv2
import numpy as np
import pytest
from test_e2e_share_report import _inputs

from scripts.e2e.calibration_report import sanitize_calibration
from scripts.e2e.share_report import MAX_REPORT_BYTES, export_report
from valorant_ai_coach.hud.spectator import (
    PanelReference,
    component_match_diagnostics,
    detect_panel,
    generate_panel_reference,
    local_component_scores,
    panel_components,
)
from valorant_ai_coach.hud.templates import HudTemplateProfile


def panel(panel_images, y=8, fragmented=False):
    image = cv2.cvtColor(panel_images(160, 126)[0], cv2.COLOR_BGR2GRAY)
    image[:20] = 60
    split = 45 if y == 96 else 72
    for left, right in ((5, split), (split + 8, 155)) if fragmented else ((5, 155),):
        cv2.line(image, (left, y), (right, y), 230, 2)
    return image


@pytest.mark.parametrize("y", [8, 40, 96])
@pytest.mark.parametrize("fragmented", [False, True])
@pytest.mark.parametrize("shift", [-2, -1, 0, 1, 2])
def test_component_contract_all_topologies_fragments_and_rigid_offsets(
    panel_images, y, fragmented, shift
):
    image = panel(panel_images, y, fragmented)
    reference = panel_components(image)
    assert isinstance(reference, PanelReference)
    shifted = cv2.warpAffine(
        image, np.float32([[1, 0, shift], [0, 1, -shift]]), (160, 126), borderValue=60
    )
    result = component_match_diagnostics(shifted, reference)
    assert result["passed"]
    assert result["dx"] == shift and result["dy"] == -shift
    assert min(local_component_scores(shifted.copy(), reference.copy())) == 1
    for component in result["components"]:
        assert component["matched_expected_count"] == component["expected_count"]
        assert component["matched_observed_count"] == component["observed_count"]


def test_old_neighbourhood_contract_can_reject_its_own_valid_source(panel_images):
    image = panel(panel_images)
    # Adjacent real decoration changes which structural frame is selected;
    # the legacy precision neighbourhood includes edges absent from its labels.
    cv2.line(image, (6, 3), (154, 3), 230, 1)
    diagnostics = {}
    reference = panel_components(image, diagnostics)
    assert reference is not None
    legacy = diagnostics["legacy_self_match"]
    assert legacy["passed"] is False
    assert legacy["limiting_component"] == "portrait"
    assert legacy["components"][1]["precision"] < 0.90
    assert min(local_component_scores(image.copy(), reference)) == 1


def test_outside_support_edges_do_not_corrupt_precision(panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    cv2.rectangle(image, (115, 105), (145, 120), 220, 2)
    assert min(local_component_scores(image, reference)) == 1


def test_inside_support_conflict_lowers_precision_and_blocks_presence(panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    cv2.line(image, (5, 32), (5, 83), 230, 1)
    result = component_match_diagnostics(image, reference)
    assert result["components"][1]["precision"] < 0.90
    assert result["components"][0]["score"] >= 0.90
    assert result["components"][2]["score"] >= 0.90
    assert detect_panel(image, reference)["checked"] is False
    assert detect_panel(image, reference)["panel_present"] is None


@pytest.mark.parametrize("kind", ["portrait", "text", "boundary", "partial", "independent"])
def test_single_or_incoherent_components_are_not_positive_or_clear(panel_images, kind):
    image = panel(panel_images)
    reference = panel_components(image)
    if kind == "portrait":
        image[:20] = 60
        image[:, 50:] = 60
    elif kind == "text":
        image[:20] = 60
        image[:, :50] = 60
    elif kind == "boundary":
        image[20:] = 60
    elif kind == "partial":
        image[35:90, 50:] = 60
    else:
        text = image[25:90, 50:].copy()
        image[25:90, 50:] = cv2.warpAffine(
            text, np.float32([[1, 0, 8], [0, 1, 0]]), (110, 65), borderValue=60
        )
    result = detect_panel(image, reference)
    assert result["checked"] is False
    assert result["panel_present"] is None


def test_reference_assets_roundtrip_and_missing_support_fail_closed(tmp_path, panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    assert isinstance(reference, PanelReference)
    for name, pixels in (
        ("template", reference),
        ("support_regions", reference.regions),
        ("orientation", reference.orientation),
    ):
        ok, encoded = cv2.imencode(".png", pixels)
        assert ok
        (tmp_path / f"{name}.png").write_bytes(encoded.tobytes())
    config = {
        "version": 2,
        **{k: f"{k}.png" for k in ("template", "support_regions", "orientation")},
    }
    raw = {"schema_version": "1.0", "spectator_panel_detector": config}
    profile = HudTemplateProfile(tmp_path / "profile.json", raw)
    assert isinstance(profile._panel_components, PanelReference)
    assert min(local_component_scores(image, profile._panel_components)) == 1
    assert {p.name for p in profile._find_asset_paths(profile.raw)} == {
        "template.png",
        "support_regions.png",
        "orientation.png",
    }
    config["support_regions"] = "missing.png"
    invalid = HudTemplateProfile(tmp_path / "bad.json", raw)
    assert invalid._panel_components is None
    assert invalid.reader_diagnostics


def test_failed_support_diagnostics_self_scores_private_bounded_and_local_unchanged(
    panel_images, tmp_path
):
    image = panel(panel_images)
    stats = {}
    assert generate_panel_reference([image, image, *[np.zeros_like(image)] * 6], stats) is None
    candidate = stats["candidate_support"][0]
    assert candidate["training_support"] == 1
    assert candidate["self_match"]["passed"] is True
    assert candidate["self_match"]["minimum_score"] == 1
    assert candidate["failed_support_scores"]["count"] == 3
    assert candidate["failed_support_scores"]["max"] == 0
    candidate["self_match"]["path"] = "PRIVATE"
    candidate["self_match"]["components"][0]["OCR"] = "PRIVATE"
    stats["candidate_support"] = [
        {**copy.deepcopy(candidate), "sample_index": i} for i in range(64)
    ]
    raw = {
        "schema_version": 1,
        "automatic_identity_generation": {"references": {"spectator_panel": stats}},
    }
    before = copy.deepcopy(raw)
    shared = sanitize_calibration(raw)
    gen = shared["automatic_identity_generation"]["references"]["spectator_panel"][
        "spectator_generation"
    ]
    assert gen["matcher"] == "oriented_component_regions_v2"
    assert len(gen["candidate_support"]) == 6
    assert gen["omitted_candidate_support_count"] == 58
    assert gen["self_match_summary"]["passed_count"] == 64
    assert gen["self_match_summary"]["min"] == 1
    assert gen["candidate_support"][0]["self_match"] == {
        k: v for k, v in candidate["self_match"].items() if k != "path"
    } | {
        "components": [
            {k: v for k, v in c.items() if k != "OCR"}
            for c in candidate["self_match"]["components"]
        ]
    }
    assert "PRIVATE" not in json.dumps(shared)
    assert len(json.dumps(shared, indent=2).encode()) < 128 * 1024
    inputs = _inputs(tmp_path)
    inputs["raw"]["hud_calibration_diagnostics"] = raw
    export_report(**inputs)
    for name in ("summary.json", "hud_calibration.json"):
        output = tmp_path / name
        assert output.stat().st_size <= MAX_REPORT_BYTES
        assert "PRIVATE" not in output.read_text()
    assert raw == before


def test_opposing_small_component_shifts_do_not_have_a_common_transform(panel_images):
    image = panel(panel_images)
    reference = panel_components(image)
    result = np.full_like(image, 60)
    for start, end, dy in ((0, 20, -2), (25, 90, 2)):
        region = image[start:end].copy()
        result[start:end] = cv2.warpAffine(
            region, np.float32([[1, 0, 0], [0, 1, dy]]), (160, end - start), borderValue=60
        )
    match = component_match_diagnostics(result, reference)
    assert match["passed"] is False
    assert detect_panel(result, reference)["panel_present"] is None


@pytest.mark.parametrize("seed", range(5))
def test_dense_texture_around_incomplete_panel_is_not_positive(panel_images, seed):
    image = panel(panel_images)
    reference = panel_components(image)
    image[20:, 50:] = np.random.default_rng(seed).integers(0, 256, (106, 110), np.uint8)
    result = detect_panel(image, reference)
    assert result["checked"] is False
    assert result["panel_present"] is None
