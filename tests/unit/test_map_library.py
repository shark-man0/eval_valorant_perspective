from fractions import Fraction

import pytest

from valorant_ai_coach.application.map_library import (
    list_map_packages,
    open_map_package,
    publish_map_package,
)
from valorant_ai_coach.recordings.catalog import LeakageError, RecordingCatalog
from valorant_ai_coach.temporal import viewer
from valorant_ai_coach.temporal.application import build_application_timeline
from valorant_ai_coach.temporal.game import DevelopmentGameTimeline
from valorant_ai_coach.temporal.map_recorder_path import VERSION, join_recorder_seconds
from valorant_ai_coach.temporal.map_timeline_report import load_map_timeline
from valorant_ai_coach.temporal.replay import file_sha, write_private


def make_package(tmp_path, *, split="DEVELOPMENT"):
    catalog = RecordingCatalog.create(tmp_path / "catalog")
    media = tmp_path / "recording.mp4"
    media.write_bytes(b"registered bytes")
    rid = catalog.register(media, split=split, confirm_distinct=True).recording_id
    record = catalog.state.recordings[rid]
    source = {
        "video_id": rid, "source_sha256": record.source_sha256,
        "physical_match_id": record.physical_match_id,
    }
    data = build_application_timeline(
        DevelopmentGameTimeline().rebuild(), source=source, duration=Fraction(2),
        origin=Fraction(0),
    )
    bundle = tmp_path / "timeline_PRIVATE.json"
    write_private(bundle, data)
    write_private(tmp_path / "completion_PRIVATE.json", {
        "output_sha256s": {bundle.name: file_sha(bundle)},
    })
    standard, recovered = [tmp_path / f"{mode}_PRIVATE.json" for mode in ("standard", "recovered")]
    report = {
        "schema": VERSION, "qualified": False, "formal_outputs": 0, "segments": [],
        "timeline_sha256": file_sha(bundle), "interpolated_samples": 0,
    }
    report["second_rows"] = join_recorder_seconds(report, data)
    write_private(standard, report)
    write_private(recovered, {**report, "primary_report_sha256": file_sha(standard)})
    write_private(recovered.with_suffix(".display.json"), {
        "schema": "development_map_display_v1", "formal_outputs": 0,
        "report_sha256": file_sha(recovered), "atlases": [],
    })
    policy, evaluation = (tmp_path / f"{name}_PRIVATE.json" for name in ("policy", "assessment"))
    write_private(policy, {"catalog": str(catalog.root), "allowed_recording_ids": [rid]})
    assessment = {
        "source": {"source_id": rid, "physical_match_id": record.physical_match_id},
        "formal_outputs": 0, "formal_promotion": None, "development_map": {
            "formal_outputs": 0, "summary": load_map_timeline(recovered, bundle, data)["summary"],
        },
    }
    write_private(evaluation, assessment)
    return {
        "bundle": bundle, "policy": policy, "standard": standard, "recovered": recovered,
        "evaluation": evaluation,
    }


def test_map_library_reuses_exact_package_and_rejects_changed_output(tmp_path, monkeypatch):
    package = make_package(tmp_path)
    library = tmp_path / "library"
    receipt = publish_map_package(library, label="Local match", **package)
    assert publish_map_package(library, label="Local match", **package) == receipt
    assert [p.label for p in list_map_packages(library)] == ["Local match"]
    sentinel = object()
    opened = []

    def open_view(*args, **kwargs):
        opened.append((args, kwargs))
        return sentinel

    monkeypatch.setattr(viewer, "make_server", open_view)
    assert open_map_package(receipt) is sentinel
    assert opened[0][1]["evaluation_path"] == package["evaluation"]
    with package["evaluation"].open("ab") as output:
        output.write(b" ")
    with pytest.raises(ValueError, match="bound Map library artifact"):
        open_map_package(receipt)


def test_resumable_map_stage_reuses_only_sealed_bytes(tmp_path, monkeypatch):
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "scripts/map_learning"))
    from checkpoints import run_stage

    file = tmp_path / "result.json"
    file.write_bytes(b"unfinished")
    calls = []

    def build():
        calls.append(1)
        file.write_bytes(b"finished")

    run_stage(tmp_path, "result", (file.name,), build)
    run_stage(tmp_path, "result", (file.name,), build)
    assert calls == [1]
    assert len(list(tmp_path.glob("result.json.interrupted-*"))) == 1
    file.write_bytes(b"changed")
    with pytest.raises(ValueError, match="sealed Map checkpoint"):
        run_stage(tmp_path, "result", (file.name,), build)


def test_map_library_refuses_protected_recordings(tmp_path):
    package = make_package(tmp_path, split="QUALIFICATION")
    with pytest.raises(LeakageError):
        publish_map_package(tmp_path / "library", label="Protected test", **package)
    assert not (tmp_path / "library").exists()
