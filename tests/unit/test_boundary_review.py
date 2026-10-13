import hashlib
import json
import sys

import pytest

from scripts.diagnostics import prepare_boundary_review
from scripts.diagnostics.prepare_boundary_review import (
    review_html,
    review_schedule,
    uniform_schedule,
    validate_review_pts,
)
from valorant_ai_coach.video import FrameSample, VideoMetadata


def test_overview_is_fixed_source_schedule_not_boundary_prediction():
    assert uniform_schedule(91, 30) == [0, 30, 60, 90]
    assert uniform_schedule(90, 30) == [0, 30, 60]


def test_precise_review_window_keeps_original_timebase():
    assert review_schedule(100, .25, [30, 31]) == [30, 30.25, 30.5, 30.75]
    assert review_schedule(91, 30, None) == [0, 30, 60, 90]
    with pytest.raises(ValueError):
        review_schedule(100, .25, [30, 100])


def test_fractional_schedule_never_requests_exclusive_end():
    times = review_schedule(1000, 1 / 60, [119.55, 119.75])
    assert len(times) == 12
    assert all(119.55 <= point < 119.75 for point in times)


@pytest.mark.parametrize("window", [[848.4, 849.2], [914.9, 915.7]])
def test_decimal_step_does_not_round_into_excluded_native_endpoint(window):
    times = review_schedule(2214.272, .1, window)
    assert len(times) == 8
    assert all(window[0] <= round(point, 6) < window[1] for point in times)


@pytest.mark.parametrize("times", [
    [1, 1], [2, 1], [float("nan")], [float("inf")], [-1], [10],
])
def test_invalid_native_pts_cannot_be_review_evidence(times):
    with pytest.raises(ValueError):
        validate_review_pts(times, 10)


def test_sparse_source_pts_are_not_misrepresented_as_continuity_proof():
    validate_review_pts([0.0, 2.0, 9.99], 10)


@pytest.mark.parametrize("duration,step", [(0, 30), (10, 0), (float("nan"), 30), (20000, 1)])
def test_invalid_or_unbounded_overview_rejects(duration, step):
    with pytest.raises(ValueError):
        uniform_schedule(duration, step)


def test_review_page_escapes_assets_and_does_not_label_source_as_gt():
    text = review_html([{"image": 'frames/"<img>.jpg', "source_frame_pts": 3.14159}])
    assert 'src="frames/&quot;&lt;img&gt;.jpg"' in text
    assert "NOT ground truth" in text
    assert "PTS 3.141590" in text
    assert "unreviewed source evidence" in text


@pytest.mark.parametrize("complete", [True, False])
@pytest.mark.parametrize("pts_fault", [None, "duplicate", "nonfinite", "reversed"])
@pytest.mark.parametrize("playback", [False, True])
def test_review_cli_uses_native_frame_sample_and_keeps_approval_pending(
    tmp_path, monkeypatch, complete, pts_fault, playback,
):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"recording")
    digest = hashlib.sha256(b"recording").hexdigest()
    output = tmp_path / "review"

    class Video:
        def __init__(self, *args):
            pass

        def probe(self, path):
            return VideoMetadata(source, 91, 1920, 1080, 60, "h264", None, False, 9)

        def extract_frames(self, path, schedule, frame_output, **kwargs):
            assert schedule == [0, 30, 60, 90]
            assert kwargs["max_dimension"] is None
            frame_output.mkdir()
            samples = []
            for index, requested in enumerate(schedule if complete else schedule[:2]):
                image = frame_output / f"frame_{index}.jpg"
                image.write_bytes(f"source frame {index}".encode())
                samples.append(FrameSample(requested + .001, image))
            if pts_fault == "duplicate":
                samples[1] = FrameSample(samples[0].time_sec, samples[1].path)
            elif pts_fault == "nonfinite":
                samples[0] = FrameSample(float("nan"), samples[0].path)
            elif pts_fault == "reversed":
                samples.reverse()
            return samples

    monkeypatch.setattr(prepare_boundary_review, "VideoService",
                        lambda: type("Backend", (), {"ffprobe_path": "ffprobe"})())
    monkeypatch.setattr(prepare_boundary_review, "CachedVideoService", Video)
    monkeypatch.setattr(
        prepare_boundary_review, "decoder_fingerprints", lambda _: ("probe", "frame"),
    )
    monkeypatch.setattr(sys, "argv", [
        "review", "--video", str(source), "--video-id", "match_002",
        "--source-sha256", digest, "--output", str(output),
    ])
    if playback:
        sys.argv.append("--include-source-playback")
    if not complete:
        with pytest.raises(ValueError, match="incomplete"):
            prepare_boundary_review.main()
        assert not (output / "review_evidence.json").exists()
        return
    if pts_fault:
        with pytest.raises(ValueError, match="PTS"):
            prepare_boundary_review.main()
        assert not (output / "review_evidence.json").exists()
        assert not (output / "index.html").exists()
        return
    prepare_boundary_review.main()
    report = json.loads((output / "review_evidence.json").read_text())
    assert report["source_video_sha256"] == digest
    assert report["recognizer_outputs_consulted"] is False
    assert report["independent_review_status"] == "pending"
    assert report["annotations"] == []
    assert report["source_playback_available"] is playback
    assert report["window_continuity_certified"] is False
    page = (output / "index.html").read_text()
    assert ("<video" in page) is playback
    if playback:
        assert source.resolve().as_uri() + "#t=0.000000,91.000000" in page
    assert [row["source_frame_pts"] for row in report["frames"]] == [.001, 30.001, 60.001, 90.001]
    assert all(row["annotation_status"] == "unreviewed" for row in report["frames"])
    assert all(len(row["evidence_frame_sha256"]) == 64 for row in report["frames"])
    assert not (output / "MANIFEST.json").exists()


def test_review_cli_rejects_decode_rounding_across_exclusive_window_end(tmp_path, monkeypatch):
    source, output = tmp_path / "video.mp4", tmp_path / "review"
    source.write_bytes(b"recording")

    class Video:
        def probe(self, path):
            return VideoMetadata(source, 91, 1920, 1080, 60, "h264", None, False, 9)

        def extract_frames(self, path, schedule, frame_output, **kwargs):
            assert schedule == [30, 30.1, 30.2]
            frame_output.mkdir()
            image = frame_output / "frame.jpg"
            image.write_bytes(b"frame")
            return [FrameSample(time, image) for time in [30, 30.1, 30.205]]

    monkeypatch.setattr(prepare_boundary_review, "VideoService",
                        lambda: type("Backend", (), {"ffprobe_path": "ffprobe"})())
    monkeypatch.setattr(prepare_boundary_review, "CachedVideoService", lambda *args: Video())
    monkeypatch.setattr(prepare_boundary_review, "decoder_fingerprints", lambda _: ("p", "f"))
    monkeypatch.setattr(sys, "argv", [
        "review", "--video", str(source), "--video-id", "match_002", "--step", ".1",
        "--window", "30", "30.205", "--source-sha256", hashlib.sha256(b"recording").hexdigest(),
        "--output", str(output),
    ])
    with pytest.raises(ValueError, match="outside requested"):
        prepare_boundary_review.main()
    assert not (output / "review_evidence.json").exists()
