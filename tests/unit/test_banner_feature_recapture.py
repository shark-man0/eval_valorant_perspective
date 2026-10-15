import json
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from scripts.diagnostics import recapture_banner_features as subject
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.video.service import FrameSample


@pytest.mark.parametrize("end,top,height", [(True, 50, 80), (float("nan"), 50, 80),
                                          (30, True, 80), (30, 51, 80), (30, 50, 0)])
def test_invalid_feature_selection_fails_before_pixel_access(
        tmp_path, monkeypatch, end, top, height):
    def reject(*_):
        pytest.fail("invalid selection must not open pixels")
    monkeypatch.setattr(subject.cv2, "imread", reject)
    with pytest.raises(ValueError):
        subject.select(tmp_path, None, end, top, height)


def test_selection_never_opens_holdout_and_keeps_unlabelled_feature_provenance(
        tmp_path, monkeypatch):
    roi = SimpleNamespace(pixel_bounds=lambda *_: (0, 0, 220, 80))
    layout = SimpleNamespace(reference_resolution=(220, 80), normalized_roi=lambda _: roi)
    for i in range(3):
        (tmp_path / f"frame_{i:05d}_{i:010.3f}.jpg").write_bytes(b"synthetic")
    (tmp_path / "frame_00003_000030.000.jpg").write_bytes(b"never opened")
    crop = np.full((80, 220, 3), 30, np.uint8)
    for x in (20, 90, 160):
        cv2.rectangle(crop, (x, 25), (x + 18, 54), (240, 240, 240), -1)

    def read(path):
        assert "030.000" not in path
        return crop

    monkeypatch.setattr(subject.cv2, "imread", read)
    rows, bindings = subject.select(tmp_path, layout, 30, 20, 40)
    assert len(rows) == len(bindings) == 3
    assert all("semantic_label" not in r for r in rows)
    assert [r["requested_sec"] for r in rows] == [0, 1, 2]


def plan_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(subject, "_check_output_privacy", lambda *_: None)
    monkeypatch.setattr(subject, "decoder_fingerprints", lambda *_: ("a" * 64, "b" * 64))
    video = tmp_path / "source.bin"
    video.write_bytes(b"synthetic source")
    source = sha256_file(video)
    partition = tmp_path / "partition.json"
    partition.write_text(json.dumps({"kind": "development_holdout_partition_not_gt",
        "source_video_sha256": source,
        "development": {"start_sec_inclusive": 0, "end_sec_exclusive": 30},
        "holdout": {"start_sec_inclusive": 30, "end_sec_exclusive": 40}}), encoding="utf-8")
    path = tmp_path / "plan.json"
    plan = {"kind": "feature_selected_banner_recapture_not_qualification",
        "source_path": str(video), "source_sha256": source, "partition_path": str(partition),
        "source_resolution": [20, 20],
        "development_end_sec": 30, "requests": [{"requested_sec": i} for i in (1, 2, 3)],
        "inputs_sha256": {str(partition): sha256_file(partition)},
        "decoder_fingerprints": ["a" * 64, "b" * 64]}
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path, plan


@pytest.mark.parametrize("identity", [True, False])
def test_recapture_requires_new_decoder_identity_not_filename_timestamp(
        tmp_path, monkeypatch, identity):
    path, plan = plan_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(subject, "CachedVideoService", lambda service, *_: service)

    class Source:
        ffprobe_path = "synthetic"

        def probe(self, _):
            return SimpleNamespace(duration_sec=40, fps=60, width=20, height=20)

        def extract_frames(self, video, times, output, **kwargs):
            assert kwargs["max_dimension"] is None
            output.mkdir()
            result = []
            for i, t in enumerate(times):
                image = output / f"frame_{i:05d}_{t:010.3f}.jpg"
                image.write_bytes(b"unit image; not real source")
                frame = (FrameSample(t, image, int(t * 60), "1/60",
                                    plan["source_sha256"], sha256_file(image))
                         if identity else FrameSample(t, image))
                result.append(frame)
            return result

    monkeypatch.setattr(subject, "VideoService", Source)
    output = tmp_path / "recaptured"
    if not identity:
        with pytest.raises(ValueError, match="decoder identity"):
            subject.capture(path, output)
        assert not (output / "candidate_report.json").exists()
        return
    report = subject.capture(path, output)
    assert report["events_generated"] == 0 and report["qualification_created"] is False
    assert report["independent_temporal_cohort"] is False
    assert all(r["source_pts_ticks"] == r["source_frame_pts"] * 60
               for r in report["validation_frames"])


def test_recapture_changed_inputs_fail_before_source_decode(tmp_path, monkeypatch):
    path, plan = plan_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(subject, "VideoService", lambda: SimpleNamespace(ffprobe_path="synthetic"))
    from pathlib import Path
    Path(plan["source_path"]).write_bytes(b"changed source")
    with pytest.raises(ValueError, match="changed"):
        subject.capture(path, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()
