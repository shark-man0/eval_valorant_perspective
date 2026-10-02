import copy
import json

import pytest
import test_e2e_dataset_runner as dataset_runner
from test_e2e_dataset_runner import execute, write_json
from test_e2e_share_report import _inputs

from scripts.e2e import share_report
from scripts.e2e.reexport_report import parser, reexport
from scripts.e2e.run_dataset_case import CaseError


@pytest.fixture
def case(tmp_path, monkeypatch):
    return dataset_runner.case.__wrapped__(tmp_path, monkeypatch)


def verbose():
    candidate = {
        "training_cluster_size": 32,
        "training_accept_count": 25,
        "holdout_accept_count": 24,
        "roi_bounds": [0.1, 0.1, 0.5, 0.5],
        "dimensions": [40, 40],
        "reason": "training_candidate",
        "temporal_variance": 0.12,
        "edge_persistence": 0.95,
        "stable_pixel_ratio": 0.01,
        "dynamic_pixel_ratio": 0.99,
        "mask_pixel_ratio": 0.10,
        "holdout_prevalence": 0.75,
        "edge_count": 200,
        "mask_population": 120,
        "stable_edge_ratio": 0.6,
        "orientation_consistency": 0.97,
        "training_similarity": dict(count=32, min=0.1, median=0.9, max=1),
        "holdout_similarity": dict(count=32, min=0.1, median=0.9, max=1),
        "path": "PRIVATE",
        "image": "PRIVATE",
        "OCR": "PRIVATE",
    }
    samples = []
    for index in range(64):
        samples.append(
            dict(
                sample_index=index,
                training=index % 2 == 0,
                reason="structural_rejected",
                observable=True,
                textlike=True,
                portrait_candidate_count=100,
                portrait_supported_count=1,
                portrait_geometry_count=10,
                portrait_occupancy_rejected=9,
                portrait_frame_score=0.8,
                portrait_side_scores=[0.8] * 4,
                path="PRIVATE",
                OCR="PRIVATE",
            )
        )
    return dict(
        schema_version=1,
        automatic_identity_generation={
            "version": 2,
            "sample_count": 64,
            "references": {
                "weapon_ammo_structure": dict(
                    matcher="oriented_edges_v1",
                    candidate_count=64,
                    cluster_count=64,
                    omitted_candidate_count=0,
                    selected_candidate=candidate,
                    candidates=[copy.deepcopy(candidate) for _ in range(64)],
                    rejection_counts={"fixed_edges_insufficient": 10},
                ),
                "spectator_panel": dict(
                    samples=samples,
                    evidence_counts={"observable": 64, "textlike": 64},
                    rejection_counts={"structural_rejected": 64},
                ),
            },
        },
    )


@pytest.mark.parametrize("many_failures", [False, True])
def test_verbose_shared_reports_bounded_private_and_raw_unchanged(tmp_path, many_failures):
    inputs = _inputs(tmp_path)
    inputs["raw"]["hud_calibration_diagnostics"] = verbose()
    if many_failures:
        inputs["evaluation"].update(
            {"pass": False, "failures": ["missing_point:point_1"] * 300, "failure_count": 300}
        )
    before = copy.deepcopy(inputs["raw"])
    share_report.export_report(**inputs)
    summary = json.loads((tmp_path / "summary.json").read_text())
    assert summary["result"]["detail_truncated"] is True
    hud = summary["hud_calibration"]
    refs = hud["automatic_identity_generation"]["references"]
    assert len(refs["weapon_ammo_structure"]["weapon_ammo_generation"]["candidates"]) <= 6
    assert refs["weapon_ammo_structure"]["omitted_candidate_count"] >= 58
    assert len(refs["spectator_panel"]["spectator_generation"]["samples"]) <= 6
    assert refs["spectator_panel"]["spectator_generation"]["evidence_counts"]["observable"] == 64
    assert (
        refs["spectator_panel"]["spectator_generation"]["portrait_statistics"][
            "portrait_candidate_count"
        ]["count"]
        == 64
    )
    assert inputs["raw"] == before
    for name in ("summary.json", "hud_calibration.json"):
        payload = (tmp_path / name).read_bytes()
        assert len(payload) <= 128 * 1024
        assert b"PRIVATE" not in payload
    assert json.loads((tmp_path / "hud_calibration.json").read_text()) == {
        "metadata": summary["metadata"],
        **hud,
    }


def test_second_fallback_removes_diagnostic_arrays(tmp_path, monkeypatch):
    inputs = _inputs(tmp_path)
    inputs["raw"]["hud_calibration_diagnostics"] = verbose()
    # Measure the summary without arrays to choose a real byte boundary between stages.
    share_report.export_report(**inputs)
    summary = json.loads((tmp_path / "summary.json").read_text())
    share_report._drop_verbose_diagnostics(summary)
    bound = len((json.dumps(summary, ensure_ascii=False, indent=2) + "\n").encode()) + 32
    monkeypatch.setattr(share_report, "MAX_REPORT_BYTES", bound)
    share_report.export_report(**inputs)
    data = json.loads((tmp_path / "summary.json").read_text())
    assert data["result"]["detail_truncated"]
    refs = data["hud_calibration"]["automatic_identity_generation"]["references"]
    assert "candidates" not in refs["weapon_ammo_structure"]["weapon_ammo_generation"]
    assert "samples" not in refs["spectator_panel"]["spectator_generation"]
    assert refs["weapon_ammo_structure"]["omitted_candidate_count"] == 64
    assert (tmp_path / "hud_calibration.json").stat().st_size <= bound


def test_reports_still_reject_if_minimal_payload_is_too_large(tmp_path, monkeypatch):
    monkeypatch.setattr(share_report, "MAX_REPORT_BYTES", 100)
    with pytest.raises(ValueError, match="size limit"):
        share_report.export_report(**_inputs(tmp_path))
    assert not (tmp_path / "summary.json").exists()
    assert not (tmp_path / "hud_calibration.json").exists()


def recovery_args(c, run):
    return parser().parse_args(
        [
            "--run-dir",
            str(run),
            "--video-id",
            "match_001",
            "--validation-pack",
            str(c.pack),
            "--output-dir",
            str(c.root / "recovered"),
        ]
    )


@pytest.mark.parametrize("evaluation_code", [0, 1])
def test_reexport_equals_normal_export_without_any_subprocess(case, monkeypatch, evaluation_code):
    case.state["evaluation_code"] = evaluation_code
    assert execute(case) == evaluation_code
    run = next((case.root / "outputs/e2e/match_001").iterdir())
    metadata_bytes = (run / "run_metadata.json").read_bytes()
    local_before = {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()}
    assert str(case.video).encode() not in metadata_bytes
    assert str(case.root).encode() not in metadata_bytes
    before = {
        name: (case.root / "e2e_reports/match_001" / name).read_bytes()
        for name in ("summary.json", "hud_calibration.json", "history.json")
    }
    monkeypatch.setattr(
        "subprocess.run", lambda *a, **k: pytest.fail("Analyzer/evaluator/git executed")
    )
    assert reexport(recovery_args(case, run), root=case.root) == 0
    assert {p.name: p.read_bytes() for p in run.iterdir() if p.is_file()} == local_before
    for name, payload in before.items():
        assert (case.root / "recovered" / name).read_bytes() == payload


def test_export_failure_preserves_context_and_can_recover(case, monkeypatch):
    original = share_report.export_report
    monkeypatch.setattr(
        share_report, "export_report", lambda **k: (_ for _ in ()).throw(ValueError("overflow"))
    )
    assert execute(case) == 2
    run = next((case.root / "outputs/e2e/match_001").iterdir())
    assert (run / "run_metadata.json").is_file()
    assert json.loads((run / "evaluation_report.json").read_text())["pass"] is True
    monkeypatch.setattr(share_report, "export_report", original)
    assert reexport(recovery_args(case, run), root=case.root) == 0


def test_reexport_rejects_changed_inputs_or_pack(case):
    assert execute(case) == 0
    run = next((case.root / "outputs/e2e/match_001").iterdir())
    trace = run / "e2e_trace.json"
    original = trace.read_bytes()
    trace.write_bytes(original + b" ")
    with pytest.raises(CaseError, match="INTEGRITY"):
        reexport(recovery_args(case, run), root=case.root)
    trace.write_bytes(original)
    write_json(case.pack / "tests/generated/e2e_assertions_v3.json", {"changed": True})
    with pytest.raises(CaseError, match="PACK_MISMATCH"):
        reexport(recovery_args(case, run), root=case.root)


def test_legacy_recovery_keeps_historical_metadata_unknown(case, monkeypatch):
    assert execute(case) == 0
    run = next((case.root / "outputs/e2e/match_001").iterdir())
    (run / "run_metadata.json").unlink()
    monkeypatch.setattr("subprocess.run", lambda *a, **k: pytest.fail("Analyzer/git executed"))
    assert reexport(recovery_args(case, run), root=case.root) == 0
    meta = json.loads((case.root / "recovered/summary.json").read_text())["metadata"]
    for key in ("analyzer_commit", "git_is_dirty", "executed_at", "settings_fingerprint"):
        assert meta[key] is None
    assert meta["source_sha256"]


def test_optional_layout_and_map_require_recorded_evidence(case):
    layout = case.root / "local-layout.json"
    write_json(layout, {"layout": "original"})
    case.args.hud_layout = str(layout)
    case.args.manual_map_id = "summit"
    assert execute(case) == 0
    run = next((case.root / "outputs/e2e/match_001").iterdir())
    args = recovery_args(case, run)
    args.hud_layout, args.manual_map_id = str(layout), "summit"
    assert reexport(args, root=case.root) == 0
    write_json(layout, {"layout": "changed"})
    with pytest.raises(CaseError, match="LAYOUT_UNVERIFIED"):
        reexport(args, root=case.root)
    args.hud_layout = None
    args.manual_map_id = "unknown"
    with pytest.raises(CaseError, match="MANUAL_MAP_UNVERIFIED"):
        reexport(args, root=case.root)
