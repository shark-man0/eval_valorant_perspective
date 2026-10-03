import copy
import json

import pytest
from test_e2e_share_report import _inputs

from scripts.e2e.calibration_report import sanitize_calibration, sanitize_portrait_proposal
from scripts.e2e.share_report import MAX_REPORT_BYTES, export_report


def _valid_proposal(**overrides):
    value = {
        "portrait_mode": "frameless",
        "panel_topology": "portrait_side_separator",
        "portrait_search_region": [0.10, 0.18, 0.29, 0.54],
        "portrait_region_dimensions": [58, 64],
        "portrait_edge_count": 512,
        "portrait_localized_component_count": 7,
        "portrait_x_spread": 0.86,
        "portrait_y_spread": 0.91,
        "portrait_occupied_rows": 4,
        "portrait_occupied_columns": 4,
        "portrait_orientation_distribution": [0.10, 0.12, 0.13, 0.14, 0.14, 0.13, 0.12, 0.12],
        "portrait_relative_to_text": 0.17,
        "portrait_relative_to_boundary": 0.047,
        "portrait_support_region_population": 1840,
        "portrait_candidate_rejection_reason": None,
        "frameless_rejections": {"separator_geometry": 0, "portrait_orientation": 1},
    }
    value.update(overrides)
    return value


def _diagnostics(samples, supports):
    return {
        "schema_version": 1,
        "automatic_identity_generation": {
            "version": 2,
            "sample_count": len(samples),
            "geometry_mode": "generated",
            "references": {
                "spectator_panel": {
                    "status": "generated",
                    "matcher": "oriented_component_regions_v2",
                    "training_count": 4,
                    "holdout_count": 4,
                    "training_accept_count": 4,
                    "holdout_accept_count": 4,
                    "candidate_count": len(supports),
                    "proposal_sample_count": 4,
                    "holdout_proposal_skipped_count": 4,
                    "portrait_modes": {"framed": 2, "frameless": 6, "private_mode": 999},
                    "frameless_rejection_counts": {
                        "separator_geometry": 5,
                        "two_text_rows_missing": 3,
                        "private_reason": 999,
                    },
                    "samples": samples,
                    "candidate_support": supports,
                    "frameless_candidates": [{"pixels": "PRIVATE"}] * 200,
                }
            },
        },
    }


def test_portrait_diagnostics_allowlist_accepts_known_frameless_fields():
    proposal = _valid_proposal()
    proposal.update(path="PRIVATE", raw_pixels="PRIVATE", frameless_candidates=["PRIVATE"])
    sanitized = sanitize_portrait_proposal(proposal)

    assert sanitized["portrait_mode"] == "frameless"
    assert sanitized["panel_topology"] == "portrait_side_separator"
    assert sanitized["portrait_search_region"] == [0.10, 0.18, 0.29, 0.54]
    assert sanitized["portrait_region_dimensions"] == [58, 64]
    assert sanitized["portrait_orientation_distribution"] == pytest.approx(
        proposal["portrait_orientation_distribution"]
    )
    assert sanitized["frameless_rejections"]["separator_geometry"] == 0
    assert "PRIVATE" not in json.dumps(sanitized)
    assert "frameless_candidates" not in json.dumps(sanitized)


def test_portrait_diagnostics_reject_malformed_geometry_counts_and_enums():
    malformed = _valid_proposal(
        portrait_mode="private-mode",
        panel_topology="private-topology",
        portrait_search_region=[-0.1, 0.2, 1.1, 0.9],
        portrait_region_dimensions=[0, True],
        portrait_edge_count=-1,
        portrait_localized_component_count=2.5,
        portrait_x_spread=1.01,
        portrait_y_spread=float("nan"),
        portrait_occupied_rows=5,
        portrait_occupied_columns=True,
        portrait_orientation_distribution=[0.125] * 7,
        portrait_relative_to_text=1.2,
        portrait_relative_to_boundary=-0.1,
        portrait_support_region_population=False,
        portrait_candidate_rejection_reason="PRIVATE",
        frameless_rejections={"separator_geometry": -1, "private_reason": 22},
    )
    sanitized = sanitize_portrait_proposal(malformed)

    assert sanitized["portrait_mode"] is None
    assert sanitized["panel_topology"] is None
    assert sanitized["portrait_search_region"] is None
    assert sanitized["portrait_region_dimensions"] is None
    assert sanitized["portrait_edge_count"] is None
    assert sanitized["portrait_localized_component_count"] is None
    assert sanitized["portrait_x_spread"] is None
    assert sanitized["portrait_y_spread"] is None
    assert sanitized["portrait_occupied_rows"] is None
    assert sanitized["portrait_occupied_columns"] is None
    assert sanitized["portrait_orientation_distribution"] is None
    assert sanitized["portrait_relative_to_text"] is None
    assert sanitized["portrait_relative_to_boundary"] is None
    assert sanitized["portrait_support_region_population"] is None
    assert sanitized["portrait_candidate_rejection_reason"] is None
    assert sanitized["frameless_rejections"]["separator_geometry"] is None
    assert "private_reason" not in json.dumps(sanitized)


def test_samples_and_candidates_share_only_sanitized_proposals():
    proposal = _valid_proposal()
    sample = {
        **proposal,
        "sample_index": 2,
        "training": True,
        "reason": "candidate",
        "frameless_candidates": [{"private_name": "PRIVATE", "image": "PRIVATE"}],
    }
    support = {
        "sample_index": 2,
        "training_support": 4,
        "minimum_required": 3,
        "portrait_proposal": proposal,
        "frameless_candidates": [{"private_name": "PRIVATE"}],
    }
    raw = _diagnostics([sample], [support])
    raw_before = copy.deepcopy(raw)
    report = sanitize_calibration(raw)
    generation = report["automatic_identity_generation"]["references"]["spectator_panel"][
        "spectator_generation"
    ]

    assert generation["portrait_modes"] == {"framed": 2, "frameless": 6}
    assert generation["proposal_sample_count"] == 4
    assert generation["holdout_proposal_skipped_count"] == 4
    assert generation["frameless_rejection_counts"]["separator_geometry"] == 5
    assert generation["frameless_rejection_counts"]["two_text_rows_missing"] == 3
    assert generation["samples"][0]["portrait_mode"] == "frameless"
    assert generation["samples"][0]["panel_topology"] == "portrait_side_separator"
    assert generation["candidate_support"][0]["portrait_proposal"]["portrait_mode"] == "frameless"
    assert "PRIVATE" not in json.dumps(report)
    assert "frameless_candidates" not in json.dumps(report)
    assert raw == raw_before


def test_export_bounds_compacted_frameless_telemetry_and_hides_raw_candidates(tmp_path):
    proposal = _valid_proposal()
    samples = [
        {
            **proposal,
            "sample_index": index,
            "training": index % 2 == 0,
            "reason": "candidate" if index == 0 else "structural_rejected",
            "rejection_stage": f"stage_{index}",
            "frameless_candidates": [{"path": "PRIVATE", "pixels": "X" * 4096}] * 10,
        }
        for index in range(64)
    ]
    supports = [
        {
            "sample_index": index * 2,
            "training_support": 4 if index % 2 == 0 else 1,
            "minimum_required": 3,
            "portrait_proposal": proposal,
            "frameless_candidates": [{"private_path": "PRIVATE"}] * 20,
        }
        for index in range(64)
    ]
    raw = _diagnostics(samples, supports)
    sanitized = sanitize_calibration(raw)
    generation = sanitized["automatic_identity_generation"]["references"]["spectator_panel"][
        "spectator_generation"
    ]
    assert len(generation["samples"]) <= 6
    assert len(generation["candidate_support"]) == 6
    assert generation["omitted_sample_count"] == 64 - len(generation["samples"])
    assert generation["omitted_candidate_support_count"] == 58

    inputs = _inputs(tmp_path)
    inputs["raw"]["hud_calibration_diagnostics"] = raw
    export_report(**inputs)
    for name in ("summary.json", "hud_calibration.json"):
        output = tmp_path / name
        assert output.stat().st_size <= MAX_REPORT_BYTES
        text = output.read_text(encoding="utf-8")
        assert "PRIVATE" not in text
        assert "frameless_candidates" not in text
