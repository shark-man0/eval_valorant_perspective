import copy
import json

import cv2
import numpy as np
import pytest
from test_e2e_share_report import _inputs

from scripts.e2e import share_report
from scripts.e2e.calibration_report import sanitize_calibration
from scripts.e2e.share_report import MAX_REPORT_BYTES, export_report
from valorant_ai_coach.hud.spectator import detect_panel, generate_panel_reference, panel_components


@pytest.mark.parametrize("seed", range(5))
def test_dense_texture_cannot_be_panel_or_explicit_absence(panel_images, seed):
    positive, _ = panel_images(160, 126)
    labels = panel_components(cv2.cvtColor(positive, cv2.COLOR_BGR2GRAY))
    texture = np.random.default_rng(seed).integers(0, 256, (126, 160), dtype=np.uint8)
    result = detect_panel(texture, labels)
    assert result["checked"] is False
    assert result["panel_present"] is None
    assert min(result["positive_component_scores"]) < 0.90


@pytest.mark.parametrize("repeated", [False, True])
def test_texture_only_cannot_generate_supported_reference(repeated):
    crops = [
        np.random.default_rng(0 if repeated else i).integers(0, 256, (126, 160), dtype=np.uint8)
        for i in range(16)
    ]
    stats = {}
    assert generate_panel_reference(crops, stats) is None
    assert stats.get("training_accept_count", 0) < 3
    assert all(c["training_support"] < 3 for c in stats["candidate_support"])


def test_noise_does_not_inflate_minimum_training_support(panel_images):
    positive, _ = panel_images(160, 126)
    crops = [
        positive if i < 2 else np.random.default_rng(i).integers(0, 256, (126, 160), dtype=np.uint8)
        for i in range(16)
    ]
    stats = {}
    assert generate_panel_reference(crops, stats) is None
    assert max(c["training_support"] for c in stats["candidate_support"]) == 1


def test_supported_positive_survives_mixed_texture_and_holdout(panel_images):
    positive, _ = panel_images(160, 126)
    crops = [
        positive
        if i % 4 < 2
        else np.random.default_rng(i).integers(0, 256, (126, 160), dtype=np.uint8)
        for i in range(16)
    ]
    stats = {}
    labels = generate_panel_reference(crops, stats)
    assert labels is not None
    assert stats["training_accept_count"] == stats["holdout_accept_count"] == 4
    assert detect_panel(positive, labels)["panel_present"] is True


def test_rejected_candidate_support_is_shared_without_inventing_acceptance(panel_images):
    positive, _ = panel_images(160, 126)
    stats = {}
    assert (
        generate_panel_reference(
            [positive if i < 2 else np.zeros_like(positive) for i in range(16)], stats
        )
        is None
    )
    report = sanitize_calibration(
        {
            "schema_version": 1,
            "automatic_identity_generation": {"references": {"spectator_panel": stats}},
        }
    )
    panel = report["automatic_identity_generation"]["references"]["spectator_panel"]
    assert panel["training_accept_count"] is None
    generation = panel["spectator_generation"]
    assert generation["candidate_support"][0]["training_support"] == 1
    assert generation["candidate_support_summary"]["max"] == 1
    assert generation["candidate_support_summary"]["minimum_required"] == 3


def test_shared_candidate_support_bounded_private_and_local_unchanged(tmp_path):
    stats = {
        "candidate_support": [
            dict(
                sample_index=i,
                training_support=i % 8,
                minimum_required=3,
                image="PRIVATE",
                OCR="PRIVATE",
            )
            for i in range(64)
        ]
    }
    raw = {
        "schema_version": 1,
        "automatic_identity_generation": {"references": {"spectator_panel": stats}},
    }
    before = copy.deepcopy(raw)
    report = sanitize_calibration(raw)
    assert raw == before
    generation = report["automatic_identity_generation"]["references"]["spectator_panel"][
        "spectator_generation"
    ]
    assert len(generation["candidate_support"]) == 6
    assert generation["omitted_candidate_support_count"] == 58
    assert generation["candidate_support_summary"] == dict(
        count=64, min=0, median=3.5, max=7, minimum_required=3, below_minimum_count=24
    )
    assert {0, 7} <= {s["training_support"] for s in generation["candidate_support"]}
    assert "PRIVATE" not in json.dumps(report)
    inputs = _inputs(tmp_path)
    inputs["raw"]["hud_calibration_diagnostics"] = raw
    export_report(**inputs)
    for name in ("summary.json", "hud_calibration.json"):
        path = tmp_path / name
        assert path.stat().st_size < MAX_REPORT_BYTES
        assert "PRIVATE" not in path.read_text()
    assert raw == before


def test_size_fallback_keeps_support_summary_without_representatives(tmp_path, monkeypatch):
    inputs = _inputs(tmp_path)
    inputs["raw"]["hud_calibration_diagnostics"] = {
        "schema_version": 1,
        "automatic_identity_generation": {
            "references": {
                "spectator_panel": {
                    "candidate_support": [
                        dict(sample_index=i, training_support=i % 8, minimum_required=3)
                        for i in range(64)
                    ]
                }
            }
        },
    }
    export_report(**inputs)
    summary = json.loads((tmp_path / "summary.json").read_text())
    share_report._drop_verbose_diagnostics(summary)
    bound = len((json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode()) + 32
    monkeypatch.setattr(share_report, "MAX_REPORT_BYTES", bound)
    export_report(**inputs)
    summary = json.loads((tmp_path / "summary.json").read_text())
    generation = summary["hud_calibration"]["automatic_identity_generation"]["references"][
        "spectator_panel"
    ]["spectator_generation"]
    assert "candidate_support" not in generation
    assert generation["candidate_support_summary"]["count"] == 64
    assert generation["omitted_candidate_support_count"] == 64
    assert summary["result"]["detail_truncated"] is True
    assert (tmp_path / "hud_calibration.json").stat().st_size <= bound
