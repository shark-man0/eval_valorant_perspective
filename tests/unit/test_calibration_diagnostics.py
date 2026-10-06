import json

import cv2
import numpy as np
import pytest

from scripts.e2e.calibration_report import sanitize_calibration
from scripts.e2e.share_report import export_report
from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.diagnostics import ANCHORS, CalibrationTelemetry
from valorant_ai_coach.hud.layout import CalibrationResult, HudLayout
from valorant_ai_coach.hud.templates import HudTemplateProfile
from valorant_ai_coach.resources import resource_path


def test_temporal_training_holdout_evidence_is_exported_without_private_reasons():
    report = sanitize_calibration({
        "schema_version": 1,
        "temporal_generation": {"anchors": {
            "top_match_bar": {
                "valid": True, "reason": "independent_support",
                "training_count": 32, "holdout_count": 32,
                "training_accept_count": 32, "holdout_accept_count": 31,
                "threshold": 0.94, "selected_pixels": 789, "selected_ratio": 0.005,
                "training_similarity": {"min": 0.95, "median": 0.98, "path": "PRIVATE"},
                "holdout_similarity": {"min": float("nan"), "median": 0.97},
            },
            "round_timer": {"reason": "PRIVATE", "training_count": True},
        }},
    })["temporal_generation"]["anchors"]
    selected = report["top_match_bar"]
    assert selected["training_accept_count"] == 32
    assert selected["holdout_accept_count"] == 31
    assert selected["threshold"] == 0.94
    assert selected["reason"] == "independent_support"
    assert selected["holdout_similarity"]["min"] is None
    assert report["round_timer"]["reason"] is None
    assert report["round_timer"]["training_count"] is None
    assert "PRIVATE" not in json.dumps(report)


def test_automatic_identity_export_is_allowlisted():
    unsafe = {
        "schema_version": 1,
        "automatic_identity_generation": {
            "sample_count": 32,
            "geometry_mode": "generated",
            "path": "PRIVATE",
            "references": {
                "hp_hud_structure": {
                    "status": "generated",
                    "content_hash": "a" * 64,
                    "dimensions": [20, 30],
                    "holdout_count": 16,
                    "holdout_accept_count": 15,
                    "holdout_median": 0.98,
                    "template": "PRIVATE",
                    "pixels": "PRIVATE",
                },
                "PRIVATE": {"status": "PRIVATE"},
            },
        },
    }
    result = sanitize_calibration(unsafe)["automatic_identity_generation"]
    assert "PRIVATE" not in json.dumps(result)
    row = result["references"]["hp_hud_structure"]
    assert row["holdout_accept_count"] == 15
    assert row["content_hash"] == "a" * 64
    assert row["dimensions"] == [20, 30]


def test_panel_resampling_diagnostics_are_allowlisted():
    result = sanitize_calibration({
        "schema_version": 1,
        "automatic_identity_generation": {"references": {"spectator_panel": {
            "status": "insufficient_evidence", "sampling": {
                "method": "training_proposal_neighborhoods_v1", "reason": "sampled",
                "initial_training_count": 32, "initial_holdout_count": 32,
                "requested_count": 12, "accepted_count": 12, "path": "PRIVATE",
            },
        }}},
    })["automatic_identity_generation"]["references"]["spectator_panel"]
    sampling = result["spectator_generation"]["sampling"]
    assert sampling["method"] == "training_proposal_neighborhoods_v1"
    assert sampling["initial_holdout_count"] == 32
    assert sampling["requested_count"] == sampling["accepted_count"] == 12
    assert "PRIVATE" not in json.dumps(result)


def test_cluster_and_runtime_failures_are_separately_shared():
    raw = {
        "schema_version": 1,
        "identity_missing": {"hp_hud_structure": 9, "PRIVATE": 10},
        "spectator_checks": {
            "panel_structure_ambiguous": 4,
            "panel_structure_mismatch": 2,
            "reference_unavailable": 5,
            "PRIVATE": 10,
        },
        "automatic_identity_generation": {
            "version": 2,
            "references": {
                "spectator_panel": {
                    "status": "insufficient_evidence",
                    "candidate_count": 5,
                    "structural_rejected": 2,
                    "holdout_rejected": 1,
                    "holdout_accept_count": 0,
                    "PRIVATE": "PRIVATE",
                }
            },
        },
    }
    report = sanitize_calibration(raw)
    assert report["identity_missing"] == {"hp_hud_structure": 9}
    assert report["spectator_checks"]["panel_structure_ambiguous"] == 4
    assert report["spectator_checks"]["panel_structure_mismatch"] == 2
    row = report["automatic_identity_generation"]["references"]["spectator_panel"]
    assert row["candidate_count"] == 5 and row["holdout_rejected"] == 1
    assert "PRIVATE" not in json.dumps(report)


def test_anchor_metadata_scores_and_geometry_are_separate(tmp_path):
    path = tmp_path / "private_username.png"
    cv2.imwrite(str(path), np.random.default_rng(4).integers(0, 255, (20, 30), dtype=np.uint8))
    raw = {
        "schema_version": "1.0",
        "anchors": {
            name: {
                "template": path.name,
                "threshold": 0.93,
                "mask": path.name,
            }
            for name in ANCHORS
        },
    }
    profile = HudTemplateProfile(tmp_path / "private_profile.json", raw)
    layout = HudLayout.load(resource_path("config/hud_layout_1080p_v3.json"))
    telemetry = CalibrationTelemetry(profile, layout)
    ok = CalibrationResult(True, (), 4, 0.0, 0.0)
    missing = CalibrationResult(False, ("insufficient_anchors",), 0, None, None)
    telemetry.record(dict.fromkeys(ANCHORS), dict.fromkeys(ANCHORS, 0.98), ok, ok, "unknown", 0)
    telemetry.record({}, dict.fromkeys(ANCHORS, 0.5), missing, ok, "unknown", 0)
    telemetry.record({}, {}, missing, missing, "unknown", 0)
    result = sanitize_calibration(telemetry.snapshot())
    assert result["fresh_geometry_success_rate"] == pytest.approx(1 / 3)
    assert result["effective_geometry_success_rate"] == pytest.approx(2 / 3)
    assert result["counts"]["geometry_valid_state_unknown"] == 2
    assert result["counts"]["geometry_invalid_unknown"] == 1
    assert result["counts"]["retained_geometry_frames"] == 1
    for anchor in result["anchors"]:
        assert anchor["dimensions"] == [30, 20]
        assert anchor["threshold"] == 0.93
        assert anchor["mask_presence"] is True
        assert len(anchor["content_hash"]) == 64
        assert anchor["accepted_count"] == 1
        assert anchor["rejected_count"] == 2
        assert anchor["unscored_count"] == 1
        assert anchor["match_confidence"] == {"min": 0.5, "median": 0.74, "max": 0.98}
        assert anchor["missing_during_insufficient_anchors"] == 2
        assert anchor["geometry_success_rate_when_accepted"] == 1.0
    assert "private" not in json.dumps(result)


def test_export_filters_telemetry_and_keeps_old_reports_honest(tmp_path):
    value = {
        "schema_version": 1,
        "profile_present": True,
        "anchors": [
            {
                "anchor_name": "round_timer",
                "threshold": float("nan"),
                "content_hash": "sk-secret",
                "dimensions": [1, "private"],
                "path": "D:\\Private\\anchor.png",
                "match_confidence": {"min": float("inf")},
            },
            {"anchor_name": "Private", "path": "secret"},
        ],
        "counts": {"frames": 3, "secret": "token"},
        "reasons": {"insufficient_anchors": 2, "secret": 10},
    }
    path = export_report(
        raw={"hud_calibration_diagnostics": value},
        trace={},
        evaluation={"pass": False},
        assertions={},
        metadata={},
        output_dir=tmp_path,
    )
    for content in (path.read_text(), (tmp_path / "hud_calibration.json").read_text()):
        assert all(secret not in content for secret in ("D:\\", "Private", "sk-secret", "token"))
        assert "NaN" not in content and "Infinity" not in content
    assert sanitize_calibration(None) == {"available": False}


def test_generation_stats_and_identity_codes_are_allowlisted():
    result = sanitize_calibration(
        {
            "schema_version": 1,
            "identity_reasons": {"independent_hud_structures": 10, "private-key": 5},
            "temporal_generation": {
                "sample_count": 24,
                "anchor_count": 3,
                "generated_assets_sha256": "a" * 64,
                "path": "C:\\private",
                "anchors": {
                    "round_timer": {
                        "selected_ratio": 0.2,
                        "selected_pixels": 80,
                        "secret": "secret-text",
                    }
                },
            },
        }
    )
    assert result["identity_reasons"] == {"independent_hud_structures": 10}
    assert result["temporal_generation"]["sample_count"] == 24
    assert "private" not in json.dumps(result) and "secret-text" not in json.dumps(result)


def test_rejected_anchor_scores_never_restore_live_identity(live_identity_signals):
    from unittest.mock import Mock

    analyzer = RealHudAnalyzer(resource_path("config/hud_layout_1080p_v3.json"))
    anchors = {name: analyzer.layout.normalized_roi(name) for name in ANCHORS}
    profile = Mock()
    profile.raw = {"anchors": {name: {"threshold": 0.99} for name in ANCHORS}}
    profile.detect_anchors.side_effect = [
        (anchors, dict.fromkeys(ANCHORS, 1.0), ()),
        ({}, dict.fromkeys(ANCHORS, 0.95), ()),
    ]
    profile.detect_signals.side_effect = [live_identity_signals, {}]
    analyzer.template_profile = profile
    frame = np.full((1080, 1920, 3), 60, dtype=np.uint8)
    result = analyzer.observe_frames([frame, frame])
    assert result.observations[0]["primary_state"] == "live_first_person"
    assert result.observations[1]["primary_state"] == "unknown"
    assert result.calibration.calibrated  # Missing anchors alone do not revoke geometry.
    assert result.calibration_diagnostics["counts"]["retained_geometry_frames"] == 1
