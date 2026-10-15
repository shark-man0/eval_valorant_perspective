import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from scripts.diagnostics import capture_unlabeled_banner_pool as subject
from scripts.e2e.run_dataset_case import sha256_file


def test_fixed_cadence_does_not_use_boundary_labels_or_prior_predictions():
    times = subject.fixed_times(60, [1.375, 10])
    assert all((t - 1.375) % 3 == 0 for t in times)
    assert all(0 <= t < 60 and abs(t - 1.375) >= .5 and abs(t - 10) >= .5 for t in times)


@pytest.mark.parametrize("end,previous", [(True, []), (float("inf"), []),
                                         (5, []), (1000, []), (60, [float("nan")])])
def test_sampling_limits_fail_closed(end, previous):
    with pytest.raises(ValueError):
        subject.fixed_times(end, previous)


def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(subject, "_check_output_privacy", lambda *_: None)
    monkeypatch.setattr(subject, "decoder_fingerprints", lambda *_: ("a" * 64, "b" * 64))
    monkeypatch.setattr(subject, "VideoService", lambda: SimpleNamespace(ffprobe_path="synthetic"))
    video = tmp_path / "synthetic_not_video.bin"
    video.write_bytes(b"unit source; not real video evidence")
    source = sha256_file(video)
    partition = tmp_path / "partition.json"
    partition.write_text(json.dumps({"kind": "development_holdout_partition_not_gt",
        "source_video_sha256": source,
        "development": {"start_sec_inclusive": 0, "end_sec_exclusive": 30},
        "holdout": {"start_sec_inclusive": 30, "end_sec_exclusive": 40}}), encoding="utf-8")
    history = tmp_path / "history"
    history.mkdir()
    (history / "candidate_report.json").write_text(json.dumps({"source_sha256": source,
        "validation_frames": [{"source_frame_pts": 1.375, "sha256": "c" * 64}],
        "expected_events": "poison_not_sampling_input"}), encoding="utf-8")
    path = tmp_path / "plan.json"
    plan = subject.freeze(video, source, partition, [history], path)
    return video, path, plan


def test_frozen_source_capture_has_no_ocr_or_analyzer(tmp_path, monkeypatch):
    video, path, plan = fixture(tmp_path, monkeypatch)
    before = video.read_bytes()

    class FakeSource:
        def probe(self, _):
            return SimpleNamespace(duration_sec=40, width=80, height=60, fps=60)

        def extract_frames(self, video, times, output, **kwargs):
            assert kwargs["max_dimension"] is None and kwargs["max_frames"] == 256
            output.mkdir()
            frames = []
            for i, t in enumerate(times):
                image = np.full((60, 80, 3), i + 20, np.uint8)
                target = output / f"frame_{i:03d}.jpg"
                assert cv2.imwrite(str(target), image)
                frames.append(SimpleNamespace(path=target, time_sec=t))
            return frames

    monkeypatch.setattr(subject, "CachedVideoService", lambda *_: FakeSource())
    output = tmp_path / "captured"
    result = subject.capture(path, output)
    assert result["source_only"] is True
    assert result["ocr_calls"] == result["analyzer_calls"] == result["events_generated"] == 0
    assert len(result["validation_frames"]) == len(plan["times"])
    assert video.read_bytes() == before
    assert not list(output.glob("*.global_qualification.json"))
    with pytest.raises(FileExistsError):
        subject.capture(path, output)


@pytest.mark.parametrize("fault", ["source", "time", "holdout", "decoder"])
def test_changed_source_or_sampling_contract_rejects_before_capture(tmp_path, monkeypatch, fault):
    video, path, plan = fixture(tmp_path, monkeypatch)
    if fault == "source":
        video.write_bytes(b"changed")
    elif fault == "decoder":
        monkeypatch.setattr(subject, "decoder_fingerprints", lambda *_: ("d" * 64, "e" * 64))
    else:
        plan["times"][0] = 3.5 if fault == "time" else 31
        path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(ValueError):
        subject.capture(path, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()
