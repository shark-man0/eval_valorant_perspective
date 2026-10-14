import hashlib
import json
import sys

import pytest

from scripts.diagnostics import prepare_boundary_review as review
from valorant_ai_coach.video import FrameSample, VideoMetadata


def plan(windows=((1, 3), (10, 12))):
    return {"kind": "private_source_review_plan_not_gt", "video_id": "match_x",
            "source_video_sha256": hashlib.sha256(b"source").hexdigest(),
            "production_input": False, "recognizer_outputs_consulted": False,
            "items": [{"review_item_id": f"review_{index}", "review_window_sec": list(window),
                       "approved_ground_truth": False, "event_time_sec": None,
                       "round_id": None, "continuity_status": "not_verified", "notes": "<note>"}
                      for index, window in enumerate(windows)]}


def test_plan_keeps_disjoint_timebase_and_deduplicates_overlap():
    assert review.plan_schedule(plan(), 20, 1) == [1, 2, 10, 11]
    assert review.plan_schedule(plan(((1, 3), (2, 4))), 20, 1) == [1, 2, 3]


@pytest.mark.parametrize("fault", ["gt", "event", "round", "continuity", "analyzer", "duplicate"])
def test_plan_refuses_ground_truth_or_recognizer_inputs(fault):
    value = plan()
    if fault == "analyzer":
        value["recognizer_outputs_consulted"] = True
    elif fault == "duplicate":
        value["items"][1]["review_item_id"] = "review_0"
    else:
        field, data = {"gt": ("approved_ground_truth", True), "event": ("event_time_sec", 2),
                       "round": ("round_id", "r1"),
                       "continuity": ("continuity_status", "verified")}[fault]
        value["items"][0][field] = data
    with pytest.raises(ValueError):
        review.plan_schedule(value, 20, 1)


def test_batch_is_bounded_before_decoding():
    with pytest.raises(ValueError, match="2400"):
        review.plan_schedule(plan([(i * 700, i * 700 + 600) for i in range(5)]), 4000, 1)
    with pytest.raises(ValueError):
        review.plan_schedule(plan(), 20, .00001)


@pytest.mark.parametrize("fault", [None, "source", "endpoint", "mutation", "read_mutation"])
@pytest.mark.parametrize("playback", [False, True])
def test_batch_cli_preserves_private_source_integrity_and_never_joins_windows(
    tmp_path, monkeypatch, fault, playback,
):
    source, plan_path, output = tmp_path / "source.mp4", tmp_path / "plan.json", tmp_path / "review"
    source.write_bytes(b"source")
    value = plan(((0, 599), (700, 899)))
    if fault == "source":
        value["source_video_sha256"] = "0" * 64
    plan_path.write_text(json.dumps(value), encoding="utf-8")
    chunks = []
    if fault == "read_mutation":
        original_read = type(plan_path).read_text

        def mutating_read(path, *args, **kwargs):
            data = original_read(path, *args, **kwargs)
            if path == plan_path:
                path.write_text(data + " ", encoding="utf-8")
            return data

        monkeypatch.setattr(type(plan_path), "read_text", mutating_read)

    class Video:
        def probe(self, path):
            return VideoMetadata(source, 1000, 1920, 1080, 60, "h264", None, False, 6)

        def extract_frames(self, path, schedule, folder, **kwargs):
            assert len(schedule) <= 600 and kwargs["max_dimension"] is None
            chunks.append(len(schedule))
            folder.mkdir()
            result = []
            for index, time in enumerate(schedule):
                image = folder / f"{index}.jpg"
                image.write_bytes(f"frame {time}".encode())
                result.append(FrameSample(time, image))
            if fault == "endpoint" and len(chunks) == 2:
                result[-1] = FrameSample(899, result[-1].path)
            if fault == "mutation":
                plan_path.write_text(json.dumps(value) + " ", encoding="utf-8")
            return result

    monkeypatch.setattr(review, "VideoService",
                        lambda: type("Backend", (), {"ffprobe_path": "ffprobe"})())
    monkeypatch.setattr(review, "CachedVideoService", lambda *args: Video())
    monkeypatch.setattr(review, "decoder_fingerprints", lambda _: ("probe", "frame"))
    monkeypatch.setattr(sys, "argv", ["review", "--video", str(source), "--video-id", "match_x",
                                     "--source-sha256", value["source_video_sha256"],
                                     "--review-plan", str(plan_path), "--step", "1",
                                     "--output", str(output)])
    if playback:
        sys.argv.append("--include-source-playback")
    # Keep video hash valid so a wrong plan is rejected specifically as plan identity.
    if fault == "source":
        sys.argv[sys.argv.index("--source-sha256") + 1] = hashlib.sha256(b"source").hexdigest()
    if fault:
        with pytest.raises(ValueError):
            review.main()
        assert not (output / "review_evidence.json").exists()
        if fault == "read_mutation":
            assert chunks == []
        return
    review.main()
    report = json.loads((output / "review_evidence.json").read_text(encoding="utf-8"))
    assert chunks == [600, 198]
    assert len(report["frames"]) == 798
    assert report["window_continuity_certified"] is False
    assert report["source_playback_available"] is playback
    assert report["annotations"] == []
    assert report["schedule"]["plan_sha256"] == review.sha256_file(plan_path)
    page = (output / "tasks/review_0.html").read_text(encoding="utf-8")
    assert "../frames_00/0.jpg" in page and "NOT ground truth" in page
    assert ("<video" in page) is playback
    if playback:
        assert source.resolve().as_uri() + "#t=0.000000,599.000000" in page
        second_page = (output / "tasks/review_1.html").read_text(encoding="utf-8")
        assert source.resolve().as_uri() + "#t=700.000000,899.000000" in second_page
        assert "#t=0.000000,899.000000" not in page + second_page
    assert "&lt;note&gt;" in (output / "index.html").read_text(encoding="utf-8")
    assert source.read_bytes() == b"source"
