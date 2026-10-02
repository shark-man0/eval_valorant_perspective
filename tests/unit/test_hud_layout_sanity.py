import json

import cv2
import numpy as np
import pytest

from scripts.e2e.calibration_report import sanitize_calibration
from valorant_ai_coach.hud.spectator import detect_panel, generate_panel_reference, panel_components
from valorant_ai_coach.hud.weapon_identity import edge_features, structural_layout, weapon_reference


def layout_metrics(image):
    edges, angles = edge_features(image)
    lines = cv2.HoughLinesP(
        edges.astype(np.uint8) * 255, 1, np.pi / 180, threshold=8, minLineLength=8, maxLineGap=2
    )
    return structural_layout(edges, angles, lines)


def rich_parallel():
    image = np.full((36, 32), 40, np.uint8)
    for left, right, y in ((2, 12, 4), (16, 28, 16), (4, 16, 30)):
        cv2.line(image, (left, y), (right, y), 220, 1)
    return image


def test_parallel_but_spatially_rich_structure_passes_without_orientation_diversity():
    diag = layout_metrics(rich_parallel())
    assert diag["structural_gates"]["nonparallel"] is False
    assert diag["structural_gates"]["separated_layout"] is True
    assert diag["structural_gates"]["arrangement"] is True
    crops = []
    for _ in range(32):
        image = np.full((120, 160), 40, np.uint8)
        image[:36, :32] = rich_parallel()
        crops.append(image)
    stats = {}
    assert weapon_reference(crops, stats) is not None
    assert stats["holdout_accept_count"] == 16


@pytest.mark.parametrize("kind", ["single", "stripes", "compact", "texture"])
def test_background_and_insufficient_spread_do_not_pass(kind):
    image = np.full((80, 80), 40, np.uint8)
    if kind == "single":
        cv2.line(image, (0, 40), (79, 40), 220, 1)
    elif kind == "stripes":
        image[::10] = 220
    elif kind == "compact":
        cv2.rectangle(image, (30, 30), (45, 45), 220, 1)
    else:
        image = np.random.default_rng(9).integers(0, 255, (80, 80), dtype=np.uint8)
    diag = layout_metrics(image)
    if kind != "texture":
        assert diag["structural_gates"]["arrangement"] is False
    else:
        # Layout alone is not sufficient: texture fails complete generator gates.
        assert weapon_reference([image] * 32, {}) is None


def test_bounded_offset_panel_clusters_across_frames_and_partial_stays_unknown(panel_images):
    positive, negative = panel_images(160, 126)
    crops = []
    for i in range(32):
        dx, dy = (i % 3) - 1, ((i // 3) % 3) - 1
        crops.append(
            cv2.warpAffine(
                positive, np.float32([[1, 0, dx], [0, 1, dy]]), (160, 126), borderValue=(60, 60, 60)
            )
        )
    stats = {}
    labels = generate_panel_reference(crops, stats)
    assert labels is not None
    assert stats["training_accept_count"] >= 3
    assert stats["holdout_accept_count"] >= 3
    for crop in crops:
        assert detect_panel(crop, labels)["panel_present"] is True
    partial = negative.copy()
    partial[:20] = positive[:20]
    assert detect_panel(partial, labels)["checked"] is False
    assert detect_panel(negative, labels)["panel_present"] is False


def test_pairwise_is_not_final_geometry_and_reports_exact_rejection(panel_images):
    positive, _ = panel_images(160, 126)
    # A long boundary coexists, but does not span the portrait/text group.
    positive[:20] = 60
    cv2.line(positive, (90, 8), (159, 8), (230, 230, 230), 2)
    diag = {}
    assert panel_components(cv2.cvtColor(positive, cv2.COLOR_BGR2GRAY), diag) is None
    assert diag["boundary_portrait"] and diag["portrait_textlike"] and diag["boundary_textlike"]
    assert diag["final_rejections"]["boundary_span_insufficient"] > 0
    assert not diag["final_gates"]["boundary_span"]
    stats = {}
    assert generate_panel_reference([positive] * 32, stats) is None
    assert stats["final_rejection_counts"]["boundary_span_insufficient"] > 0


def test_structural_diagnostics_bounded_and_private(tmp_path):
    from scripts.e2e.share_report import MAX_REPORT_BYTES, export_report

    diag = layout_metrics(rich_parallel())
    diag.update(reason="training_candidate", training_accept_count=16, path="PRIVATE")
    raw = {
        "schema_version": 1,
        "automatic_identity_generation": {
            "references": {
                "weapon_ammo_structure": {"selected_candidate": diag, "candidates": [diag] * 64},
                "spectator_panel": {
                    "samples": [
                        {
                            "sample_index": i,
                            "final_gates": {"portrait": True, "PRIVATE": True},
                            "final_rejections": {"boundary_span_insufficient": 1, "PRIVATE": 2},
                            "path": "PRIVATE",
                        }
                        for i in range(64)
                    ],
                    "final_rejection_counts": {"boundary_span_insufficient": 64},
                },
            }
        },
    }
    result = sanitize_calibration(raw)
    assert "PRIVATE" not in json.dumps(result)
    refs = result["automatic_identity_generation"]["references"]
    assert (
        refs["weapon_ammo_structure"]["weapon_ammo_generation"]["selected_candidate"]["line_count"]
        > 0
    )
    assert (
        refs["spectator_panel"]["spectator_generation"]["final_rejection_counts"][
            "boundary_span_insufficient"
        ]
        == 64
    )
    export_report(
        raw={"hud_calibration_diagnostics": raw},
        trace={},
        evaluation={},
        assertions={},
        metadata={},
        output_dir=tmp_path,
    )
    assert (tmp_path / "summary.json").stat().st_size < MAX_REPORT_BYTES
    assert (tmp_path / "hud_calibration.json").stat().st_size < MAX_REPORT_BYTES
