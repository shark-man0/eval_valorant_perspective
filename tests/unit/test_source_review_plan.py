import json
import sys

import pytest

from scripts.diagnostics import assemble_source_review_plan as review


def evidence():
    return {"kind": "source_overview_not_gt", "video_id": "match_x",
            "source_video_sha256": "a" * 64, "recognizer_outputs_consulted": False,
            "source_hash_verified_after_extraction": True,
            "frames": [{"source_frame_pts": time, "evidence_frame_sha256": "b" * 64}
                       for time in [0, 10, 20]]}


def observations():
    return [{"kind": "start_review", "review_window_sec": [0, 10],
             "notes": "purchase -> action"}]


def test_review_intervals_never_become_gt_events_round_ids_or_continuity():
    notes = observations()
    notes[0].update({"approved_ground_truth": True, "event_time_sec": 5,
                     "round_id": "fabricated", "continuity_status": "verified"})
    result = review.assemble(evidence(), notes)
    row = result["items"][0]
    assert row["event_time_sec"] is None and row["round_id"] is None
    assert row["approved_ground_truth"] is False
    assert row["continuity_status"] == "not_verified"
    assert result["production_input"] is False
    assert row["evidence"][0]["evidence_frame_sha256"] == "b" * 64


@pytest.mark.parametrize("fault", ["recognizer", "unverified", "duplicate", "outside", "inverted"])
def test_unqualified_source_or_interval_is_rejected(fault):
    source, notes = evidence(), observations()
    if fault == "recognizer":
        source["recognizer_outputs_consulted"] = True
    elif fault == "unverified":
        source["source_hash_verified_after_extraction"] = False
    elif fault == "duplicate":
        source["frames"][1]["source_frame_pts"] = 0
    elif fault == "outside":
        notes[0]["review_window_sec"] = [0, 11]
    else:
        notes[0]["review_window_sec"] = [10, 0]
    with pytest.raises(ValueError):
        review.assemble(source, notes)


@pytest.mark.parametrize("fault", ["modified", "escape"])
def test_cli_checks_private_source_image_integrity_before_output(tmp_path, monkeypatch, fault):
    source = evidence()
    for index, frame in enumerate(source["frames"]):
        frame["image"] = f"frame_{index}.jpg"
        (tmp_path / frame["image"]).write_bytes(b"not matching frozen hash")
    if fault == "escape":
        source["frames"][0]["image"] = "../outside.jpg"
    manifest, notes, output = tmp_path / "source.json", tmp_path / "notes.json", tmp_path / "out"
    manifest.write_text(json.dumps(source), encoding="utf-8")
    notes.write_text(json.dumps(observations()), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["review", "--evidence", str(manifest),
                                     "--observations", str(notes), "--output", str(output)])
    with pytest.raises(ValueError, match="integrity"):
        review.main()
    assert not output.exists()


def test_cli_links_frozen_frames_and_escapes_notes_without_replacing_inputs(tmp_path, monkeypatch):
    source = evidence()
    for index, frame in enumerate(source["frames"]):
        frame["image"] = f"frame_{index}.jpg"
        path = tmp_path / frame["image"]
        path.write_bytes(f"source frame {index}".encode())
        frame["evidence_frame_sha256"] = review.sha256_file(path)
    manifest, notes, output = tmp_path / "source.json", tmp_path / "notes.json", tmp_path / "out"
    manifest.write_text(json.dumps(source), encoding="utf-8")
    observations_input = observations()
    observations_input[0]["notes"] = "<script>not markup</script>"
    notes.write_text(json.dumps(observations_input), encoding="utf-8")
    before = manifest.read_bytes(), notes.read_bytes()
    monkeypatch.setattr(sys, "argv", ["review", "--evidence", str(manifest),
                                     "--observations", str(notes), "--output", str(output)])
    review.main()
    report = json.loads((output / "review_plan.json").read_text(encoding="utf-8"))
    assert report["evidence_manifest_sha256"] == review.sha256_file(manifest)
    assert report["observation_input_sha256"] == review.sha256_file(notes)
    page = (output / "index.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;" in page and "<script>" not in page
    assert (tmp_path / "frame_0.jpg").as_uri() in page
    assert before == (manifest.read_bytes(), notes.read_bytes())
    with pytest.raises(FileExistsError):
        review.main()
