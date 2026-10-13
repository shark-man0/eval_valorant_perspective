import json
from copy import deepcopy
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from test_geometry_candidate_challenge import fixture

from scripts.diagnostics import probe_geometry_analyzer as subject
from scripts.diagnostics.probe_geometry_analyzer import build_trial
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.templates import HudTemplateProfile


def base_fixture(tmp_path, candidate):
    root = tmp_path / "base"
    root.mkdir()
    layout = root / "hud_layout.json"
    layout.write_bytes((candidate / "hud_layout.json").read_bytes())
    raw = json.loads((candidate / "hud_layout.templates.json").read_text(encoding="utf-8"))
    for spec in raw["anchors"].values():
        for key in ("template", "mask"):
            spec[key] = str((candidate / spec[key]).resolve())
    image = np.zeros((100, 160), np.uint8)
    cv2.line(image, (20, 20), (120, 80), 220, 4)
    assert cv2.imwrite(str(root / "independent.png"), image)
    raw["signals"] = {"buy_menu_grid_present": {
        "template": "independent.png", "threshold": .90}}
    raw["readers"] = {"round_timer": {"kind": "digits", "minimum_confidence": .9}}
    raw["notes"] = ["independent original profile"]
    layout.with_suffix(".templates.json").write_text(json.dumps(raw), encoding="utf-8")
    return layout, raw


def test_trial_replaces_only_geometry_preserving_independent_assets(tmp_path):
    candidate = fixture(tmp_path / "candidate")
    layout, raw = base_fixture(tmp_path, candidate)
    before = sha256_file(layout.with_suffix(".templates.json"))
    receipt = build_trial(layout, candidate, tmp_path / "trial")
    trial = HudTemplateProfile.load(tmp_path / "trial/hud_layout.templates.json")
    assert trial.raw["readers"] == raw["readers"] and trial.raw["notes"] == raw["notes"]
    signal = trial.raw["signals"]["buy_menu_grid_present"]
    assert sha256_file(trial.resolve_asset(signal["template"])) == sha256_file(
        layout.parent / "independent.png")
    assert signal["threshold"] == .90
    assert all(spec["threshold"] == .90 for spec in trial.raw["anchors"].values())
    assert receipt["production_adopted"] is False
    assert receipt["global_qualification_inherited"] is False
    assert receipt["identity_assets_generated"] is False
    assert not (tmp_path / "trial/hud_layout.global_qualification.json").exists()
    assert sha256_file(layout.with_suffix(".templates.json")) == before
    with pytest.raises(FileExistsError):
        build_trial(layout, candidate, tmp_path / "trial")


def test_geometry_cannot_become_an_identity_reference_even_under_another_filename(tmp_path):
    candidate = fixture(tmp_path / "candidate")
    layout, raw = base_fixture(tmp_path, candidate)
    spec = next(iter(raw["anchors"].values()))
    (layout.parent / "independent.png").write_bytes(
        HudTemplateProfile.load(candidate / "hud_layout.templates.json").resolve_asset(
            spec["template"]).read_bytes())
    with pytest.raises(ValueError, match="reused as independent"):
        build_trial(layout, candidate, tmp_path / "trial")


def test_trial_cannot_lower_existing_anchor_threshold(tmp_path):
    candidate = fixture(tmp_path / "candidate")
    layout, raw = base_fixture(tmp_path, candidate)
    raw["anchors"]["round_timer"]["threshold"] = .95
    layout.with_suffix(".templates.json").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="threshold"):
        build_trial(layout, candidate, tmp_path / "trial")


def test_trial_does_not_rewrite_layout_to_fit_candidate(tmp_path):
    candidate = fixture(tmp_path / "candidate")
    layout, _ = base_fixture(tmp_path, candidate)
    original = layout.read_bytes()
    layout.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="identical"):
        build_trial(layout, candidate, tmp_path / "trial")
    assert layout.read_bytes() == original + b" "


def test_modified_candidate_rejected_before_trial_output(tmp_path):
    candidate = fixture(tmp_path / "candidate")
    layout, _ = base_fixture(tmp_path, candidate)
    path = candidate / "hud_layout.templates.json"
    raw = deepcopy(json.loads(path.read_text(encoding="utf-8")))
    raw["signals"] = {"unsafe": True}
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="frozen"):
        build_trial(layout, candidate, tmp_path / "trial")
    assert not (tmp_path / "trial").exists()


@pytest.mark.parametrize("fault", ["missing_observation", "generated_event"])
def test_point_probe_rejects_missing_output_or_temporal_events(tmp_path, monkeypatch, fault):
    from test_round_package_builder import observation

    candidate = fixture(tmp_path / "candidate")
    layout, _ = base_fixture(tmp_path, candidate)
    video = tmp_path / "source.mp4"
    video.write_bytes(b"synthetic source for interface tests, not video accuracy")
    report_path = candidate / "candidate_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["source_sha256"] = sha256_file(video)
    report["validation_frames"][0]["source_frame_pts"] = .5
    report_path.write_text(json.dumps(report), encoding="utf-8")
    fingerprint = candidate / "candidate_fingerprint.json"
    frozen = json.loads(fingerprint.read_text(encoding="utf-8"))
    frozen[report_path.name] = sha256_file(report_path)
    fingerprint.write_text(json.dumps(frozen), encoding="utf-8")
    monkeypatch.setattr(subject, "summarize", lambda *_: {
        "candidate_report_sha256": sha256_file(report_path)})
    monkeypatch.setattr(subject, "VideoService", lambda: SimpleNamespace(probe=lambda _: None))

    class FakeAnalyzer:
        template_profile = object()
        global_qualification = None

        def observe_frames(self, frames, metadata, *, _build_events):
            assert _build_events is False and [f.time_sec for f in frames] == [.5]
            return SimpleNamespace(
                observations=[] if fault == "missing_observation" else [observation(.5)],
                hud_events=[{"type": "round_start"}] if fault == "generated_event" else [],
                calibration_diagnostics={}, diagnostics=[])

    monkeypatch.setattr(subject, "RealHudAnalyzer", lambda _: FakeAnalyzer())
    with pytest.raises(ValueError, match="coverage|generated events"):
        subject.probe(video, layout, candidate, tmp_path / "review", tmp_path / "approval",
                      tmp_path / "probe")
