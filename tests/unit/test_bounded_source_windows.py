"""Bounded source evidence tests use only synthetic lossless video."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from argparse import ArgumentTypeError
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.diagnostics.inspect_bounded_source_windows import (
    inspect_windows,
    parse_window,
)
from valorant_ai_coach.video import VideoService
from valorant_ai_coach.video.service import VideoProbeError


@pytest.fixture
def source(tmp_path: Path) -> tuple[Path, str, VideoService]:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("FFmpeg/ffprobe required for native decoder contract test")
    video = tmp_path / "synthetic.mkv"
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i",
         "testsrc=size=64x48:rate=6", "-t", "2", "-c:v", "ffv1", str(video)],
        check=True, capture_output=True, timeout=30,
    )
    digest = hashlib.sha256(video.read_bytes()).hexdigest()
    service = VideoService(ffprobe_path=ffprobe, ffmpeg_path=ffmpeg)
    return video, digest, service


def test_rational_endpoint_selects_exact_pts_after_float_expansion(source) -> None:
    video, digest, service = source
    epsilon = Fraction(1, 10**30)
    report = inspect_windows(
        video, digest, [(Fraction(1, 3) + epsilon, Fraction(1))],
        max_png_bytes=1_000_000, service=service,
    )
    window = report["windows"][0]
    ticks, base = window["selected_first_pts"]
    assert Fraction(ticks) * Fraction(base) > Fraction(1, 3)
    assert window["selected_native_frames"] >= 2
    assert window["decode_window_sec"][0] < float(Fraction(1, 3))
    assert report["whole_source_pts_pixels_verified"] is False
    assert report["cross_window_continuity_asserted"] is False
    assert report["recognition_executed"] is False
    assert len(window["native_pts_pixel_sequence_sha256"]) == 64
    assert str(video) not in str(report)


def test_sub_float_tick_boundaries_exclude_both_endpoint_frames(source) -> None:
    video, digest, service = source
    epsilon = Fraction(1, 10**30)
    # FFV1 in this Matroska fixture has frames at .333, .500, .667 and .833.
    # Both bounds round back onto an existing PTS when converted to float.
    report = inspect_windows(
        video, digest, [(Fraction(333, 1000) + epsilon, Fraction(833, 1000) - epsilon)],
        max_png_bytes=1_000_000, service=service,
    )
    window = report["windows"][0]
    first_tick, first_base = window["selected_first_pts"]
    last_tick, last_base = window["selected_last_pts"]
    assert Fraction(first_tick) * Fraction(first_base) == Fraction(1, 2)
    assert Fraction(last_tick) * Fraction(last_base) == Fraction(667, 1000)
    assert window["selected_native_frames"] == 2


def test_cli_rejects_public_output_before_inspecting_source(monkeypatch, tmp_path) -> None:
    from scripts.diagnostics import inspect_bounded_source_windows as tool

    def reject(path):
        raise ValueError("output is not private")

    monkeypatch.setattr(tool, "_check_output_privacy", reject)
    monkeypatch.setattr(sys, "argv", [
        "inspect", "--video", str(tmp_path / "missing.mkv"),
        "--source-sha256", "a" * 64, "--window", "0:1", "--max-png-bytes", "1000",
        "--output", str(tmp_path / "public.json"),
    ])
    with pytest.raises(ValueError, match="not private"):
        tool.main()


def test_cli_preserves_file_created_while_inspection_runs(monkeypatch, tmp_path) -> None:
    from scripts.diagnostics import inspect_bounded_source_windows as tool

    output = tmp_path / "receipt.json"

    def inspect(*args, **kwargs):
        output.write_text("preserve this earlier run", encoding="utf-8")
        return {"scope": "test", "windows": []}

    monkeypatch.setattr(tool, "inspect_windows", inspect)
    monkeypatch.setattr(sys, "argv", [
        "inspect", "--video", str(tmp_path / "missing.mkv"),
        "--source-sha256", "a" * 64, "--window", "0:1", "--max-png-bytes", "1000",
        "--output", str(output),
    ])
    with pytest.raises(FileExistsError):
        tool.main()
    assert output.read_text(encoding="utf-8") == "preserve this earlier run"


def test_windows_are_separate_epochs_and_terminally_verified(source) -> None:
    video, digest, service = source
    report = inspect_windows(
        video, digest,
        [(Fraction(0), Fraction(1, 2)), (Fraction(1), Fraction(3, 2))],
        max_png_bytes=1_000_000, service=service,
    )
    assert len(report["windows"]) == 2
    assert report["windows"][0]["source_epoch"] != report["windows"][1]["source_epoch"]
    assert all(row["source_terminal_verified"] for row in report["windows"])
    assert report["source_terminal_verified"] is True
    assert report["peak_retained_png_bytes"] <= report["max_window_png_bytes"]


@pytest.mark.parametrize(
    "windows,budget",
    [
        ([], 10),
        ([(Fraction(0), Fraction(1)), (Fraction(1), Fraction(2))], 10),
        ([(Fraction(1), Fraction(2)), (Fraction(0), Fraction(1))], 10),
        ([(Fraction(1), Fraction(1))], 10),
        ([(Fraction(0), Fraction(1))], 0),
    ],
)
def test_invalid_windows_fail_before_decoder_or_source_io(windows, budget, tmp_path: Path) -> None:
    class NoDecode:
        def native_window(self, *args, **kwargs):
            pytest.fail("invalid request reached native decoder")

    missing_video = tmp_path / "not-read.mkv"
    with pytest.raises(ValueError, match="ordered, disjoint"):
        inspect_windows(missing_video, "a" * 64, windows,
                        max_png_bytes=budget, service=NoDecode())  # type: ignore[arg-type]


def test_cli_window_parser_preserves_exact_rational_values() -> None:
    assert parse_window("1/10:1/3") == (Fraction(1, 10), Fraction(1, 3))
    with pytest.raises(ArgumentTypeError):
        parse_window("2:1")


def test_png_cap_failure_cleans_native_temporary_files(source, tmp_path: Path) -> None:
    video, digest, service = source
    temporary_root = Path(tempfile.gettempdir())
    before = set(temporary_root.glob("valorant-native-*"))
    with pytest.raises((VideoProbeError, ValueError), match="budget exceeded"):
        inspect_windows(video, digest, [(Fraction(0), Fraction(1))],
                        max_png_bytes=1, service=service)
    after = set(temporary_root.glob("valorant-native-*"))
    assert after == before


def test_tiny_window_scientific_float_is_expanded_safely(source) -> None:
    video, digest, service = source
    report = inspect_windows(
        video, digest, [(Fraction(1, 10**30), Fraction(1, 2))],
        max_png_bytes=1_000_000, service=service,
    )
    assert report["windows"][0]["decode_window_sec"][0] == 0
    assert report["windows"][0]["selected_native_frames"] >= 2


def test_source_mutation_during_window_fails_terminal_verification(source, monkeypatch) -> None:
    video, digest, service = source
    original = service.native_window

    @contextmanager
    def mutate_after_read(*args, **kwargs):
        with original(*args, **kwargs) as frames:
            yield frames
            video.write_bytes(video.read_bytes() + b"changed")

    monkeypatch.setattr(service, "native_window", mutate_after_read)
    with pytest.raises(VideoProbeError, match="source video changed"):
        inspect_windows(
            video, digest, [(Fraction(0), Fraction(1))],
            max_png_bytes=1_000_000, service=service,
        )
