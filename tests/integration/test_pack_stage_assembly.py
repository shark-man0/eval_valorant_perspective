import json
import sys

import pytest
from test_composed_boundary_timeline import PACK, fixture

from scripts.e2e.assemble_pack_stage import main
from scripts.e2e.compose_boundary_timeline import compose
from scripts.e2e.run_dataset_case import pack_identity, sha256_file
from scripts.e2e.runtime import CaseError


def setup(tmp_path, monkeypatch):
    timeline_root, source_root, output = (
        tmp_path / name for name in ("timeline", "source", "pack"))
    timeline_root.mkdir()
    source_root.mkdir()

    def write(root, name, value):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    timeline = compose(*fixture())
    write(timeline_root, "timeline_ground_truth_v3.json", timeline)
    negative = {"version": "3.0", "assertions": [{"id": "synthetic-safety", "window": [0, 5],
                "reason": "Synthetic actor contract", "must_not_emit_matching": {
                    "type": "round_start", "actor": "player"}}]}
    write(timeline_root, "negative_assertions_v3.json", negative)
    image = timeline_root / "assets/synthetic.jpg"
    image.parent.mkdir()
    image.write_bytes(b"synthetic image payload for byte-preservation test")
    bindings = {"source_video_sha256": "a" * 64, "evidence_bindings": [{
        "evidence_path": "assets/synthetic.jpg", "sha256": sha256_file(image)}]}
    write(timeline_root, "evidence_bindings.json", bindings)
    write(source_root, "source_video_profile_v3.json", {
        "source_filename": "synthetic.mp4", "sha256": "a" * 64, "duration_sec": 5})
    write(source_root, "frame_pts_sidecar_v3.json", {"entries": [{
        "evidence_path": "assets/synthetic.jpg"}]})
    write(source_root, "provenance.json", {
        "point_fragments_sha256": sha256_file(timeline_root / "evidence_bindings.json"),
        "source_hash_verified_after_probe": True, "source_sha256": "a" * 64})
    monkeypatch.setattr(sys, "argv", ["assemble_pack_stage", "--timeline-stage", str(timeline_root),
                                     "--source-stage", str(source_root),
                                     "--canonical-pack", str(PACK),
                                     "--output", str(output)])
    return timeline_root, source_root, output


def test_original_compiler_and_unknown_runtime_identity_are_preserved(tmp_path, monkeypatch):
    timeline, _, output = setup(tmp_path, monkeypatch)
    main()
    assert (output / "tests/build_assertions.py").read_bytes() == (
        PACK / "tests/build_assertions.py").read_bytes()
    assert (output / "tests/reference_evaluator.py").read_bytes() == (
        PACK / "tests/reference_evaluator.py").read_bytes()
    assert (output / "assets/synthetic.jpg").read_bytes() == (
        timeline / "assets/synthetic.jpg").read_bytes()
    runtime = json.loads((output / "inputs/e2e_inputs_v3.json").read_text(encoding="utf-8"))
    assert runtime["player_context"]["agent"] == "unknown"
    assert runtime["player_context"]["player_name"] == "unknown"
    assertions = json.loads((output / "tests/generated/e2e_assertions_v3.json").read_text(
        encoding="utf-8",
    ))
    assert len(assertions["required_point_events"]) == 3
    assert len(assertions["negative_assertions"]) == 11
    assert assertions["negative_assertions"][0]["id"] == "synthetic-safety"
    assert not (output / "tests/validate_pack.py").exists()
    with pytest.raises(CaseError, match="VALIDATION_PACK_MISSING"):
        pack_identity(output)  # Cannot accidentally register this unfinished staging fixture.


@pytest.mark.parametrize("fault", ["changed_binding", "changed_image", "missing_pts", "overwrite"])
def test_staging_rejects_integrity_failures(tmp_path, monkeypatch, fault):
    timeline, source, output = setup(tmp_path, monkeypatch)
    if fault == "changed_binding":
        (timeline / "evidence_bindings.json").write_text("{}")
    elif fault == "changed_image":
        (timeline / "assets/synthetic.jpg").write_bytes(b"changed")
    elif fault == "missing_pts":
        (source / "frame_pts_sidecar_v3.json").write_text('{"entries": []}')
    else:
        output.mkdir()
    with pytest.raises((ValueError, FileExistsError)):
        main()
