import importlib.util
import json

import cv2
import numpy as np
import pytest
from test_pack_stage_assembly import PACK, setup

from scripts.e2e.assemble_pack_stage import main
from scripts.e2e.validate_fixture import digest, validate


def valid_pack(tmp_path, monkeypatch):
    timeline, source, output = setup(tmp_path, monkeypatch)
    (timeline / "assets/synthetic.jpg").unlink()  # This test owns the temporary fixture.
    bindings, entries = [], []
    points = json.loads((timeline / "timeline_ground_truth_v3.json").read_text(,
        encoding="utf-8",
    ))
    for row in points["rounds"]:
        for point in row["point_events"]:
            evidence = []
            for time in point["evidence_bracket"].values():
                name = f"assets/reference_frames/synthetic_{time:.6f}s.jpg"
                evidence.append(name)
                image = timeline / name
                image.parent.mkdir(parents=True, exist_ok=True)
                ok, encoded = cv2.imencode(".jpg", np.full((8, 8, 3), 70, np.uint8))
                assert ok
                image.write_bytes(encoded.tobytes())
                bindings.append({"evidence_path": name, "sha256": digest(image)})
                entries.append({"evidence_path": name, "requested_sec": time,
                                "decoded_frame_pts_sec": time, "delta_sec": 0,
                                "packet_pts_ticks": round(time * 60), "time_base": "1/60",
                                "presentation_index": round(time * 60)})
            point["evidence"] = evidence
    (timeline / "timeline_ground_truth_v3.json").write_text(json.dumps(points),
        encoding="utf-8",
    )
    binding_path = timeline / "evidence_bindings.json"
    binding_path.write_text(json.dumps({"source_video_sha256": "a" * 64,
                                       "evidence_bindings": bindings}),
        encoding="utf-8",
    )
    (source / "frame_pts_sidecar_v3.json").write_text(json.dumps({
        "entries": entries, "frame_count_indexed": len(entries), "max_abs_delta_sec": 0}),
        encoding="utf-8",
    )
    (source / "source_video_profile_v3.json").write_text(json.dumps({
        "source_filename": "synthetic.mp4", "sha256": "a" * 64, "duration_sec": 5,
        "video_stream": {"width": 8, "height": 8, "fps": 60, "time_base": "1/60"}}),
        encoding="utf-8",
    )
    provenance = json.loads((source / "provenance.json").read_text(,
        encoding="utf-8",
    ))
    provenance["point_fragments_sha256"] = digest(binding_path)
    (source / "provenance.json").write_text(json.dumps(provenance),
        encoding="utf-8",
    )
    main()
    return output


def reseal(pack):
    """Tests-only rehashing reaches semantic guards beyond the integrity guard."""
    manifest = json.loads((pack / "MANIFEST.json").read_text(,
        encoding="utf-8",
    ))
    for name in manifest["files"]:
        manifest["files"][name] = digest(pack / name)
    (pack / "MANIFEST.json").write_text(json.dumps(manifest),
        encoding="utf-8",
    )


def test_validation_is_read_only_and_does_not_promote_staging(tmp_path, monkeypatch):
    pack = valid_pack(tmp_path, monkeypatch)
    before = (pack / "MANIFEST.json").read_bytes()
    report = validate(pack, PACK)
    assert report["rounds"] == 2 and report["images"] == 6
    assert report["formal_pack_completed"] is False
    assert (pack / "MANIFEST.json").read_bytes() == before


@pytest.mark.parametrize("fault", ["image", "pts", "bracket_order", "assertion_drift",
                                  "actor_coverage", "filename_time"])
def test_corrupt_fixture_rejected(tmp_path, monkeypatch, fault):
    pack = valid_pack(tmp_path, monkeypatch)
    if fault == "image":
        next((pack / "assets/reference_frames").glob("*.jpg")).write_bytes(b"changed")
    elif fault in {"pts", "filename_time"}:
        path = pack / "ground_truth/frame_pts_sidecar_v3.json"
        data = json.loads(path.read_text(,
            encoding="utf-8",
        ))
        data["entries"][0]["packet_pts_ticks" if fault == "pts" else "requested_sec"] = 100
        path.write_text(json.dumps(data), encoding="utf-8")
        reseal(pack)
    elif fault == "bracket_order":
        # Merely reordering keys is legal; reversing their semantic values is not.
        path = pack / "ground_truth/timeline_ground_truth_v3.json"
        data = json.loads(path.read_text(,
            encoding="utf-8",
        ))
        data["rounds"][0]["point_events"][0]["evidence_bracket"] = {
            "first_present_sec": .9, "last_absent_sec": 1}
        path.write_text(json.dumps(data), encoding="utf-8")
        reseal(pack)
    elif fault == "actor_coverage":
        path = pack / "ground_truth/negative_assertions_v3.json"
        data = json.loads(path.read_text(,
            encoding="utf-8",
        ))
        data["assertions"].pop()
        path.write_text(json.dumps(data), encoding="utf-8")
        reseal(pack)
    else:
        path = pack / "tests/generated/e2e_assertions_v3.json"
        path.write_text('{}', encoding="utf-8")
        reseal(pack)
    with pytest.raises(ValueError):
        validate(pack, PACK)


def test_extra_non_system_end_fails_with_required_boundaries_present(tmp_path, monkeypatch):
    pack = valid_pack(tmp_path, monkeypatch)
    spec = importlib.util.spec_from_file_location("actor_contract_evaluator",
                                                pack / "tests/reference_evaluator.py")
    evaluator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(evaluator)
    assertions = json.loads((pack / "tests/generated/e2e_assertions_v3.json").read_text(,
        encoding="utf-8",
    ))
    events = [{"round_id": rid, "type": kind, "actor": "system", "time_sec": time,
               "confidence": .95} for rid, kind, time in (
                   ("r1", "round_start", 1), ("r1", "round_end", 2),
                   ("r2", "round_start", 3), ("r2", "round_end", 4))]
    trace = {"events": events, "state_intervals": [], "snapshots": [], "temporal_features": []}
    assert evaluator.evaluate(assertions, trace) == []
    events.append({**events[-1], "actor": "player"})
    failures = evaluator.evaluate(assertions, trace)
    assert "negative_match:NEG-CONTRACT-round_end-player" in failures
