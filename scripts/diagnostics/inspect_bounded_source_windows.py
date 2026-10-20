"""Prove exact source PTS/pixel coverage inside explicit native windows only.

This diagnostic verifies source-bound decoder output. It makes no recognition,
continuity, lifecycle, or qualification claim and does not inspect labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import time
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

from valorant_ai_coach.video import VideoService
from valorant_ai_coach.video import native as native_module
from valorant_ai_coach.video import service as service_module
from valorant_ai_coach.video.native import NativeSourceFrame, _sha256


def validate_windows(
    windows: Sequence[tuple[Fraction, Fraction]], max_png_bytes: int,
) -> None:
    """Reject incomplete, malformed, overlapping, or touching scopes pre-I/O."""
    if (
        type(max_png_bytes) is not int or max_png_bytes <= 0 or not windows
        or any(
            not isinstance(begin, Fraction) or not isinstance(end, Fraction)
            or not 0 <= begin < end
            for begin, end in windows
        )
        or any(a[1] >= b[0] for a, b in zip(windows, windows[1:], strict=False))
    ):
        raise ValueError("ordered, disjoint, noncontact windows and positive PNG budget required")


def _file_fingerprint(path: Path) -> str:
    return _sha256(path.resolve())


def _tool_fingerprint(service: VideoService, name: str, configured: str) -> dict[str, str]:
    resolved = Path(configured)
    if not resolved.is_file():
        found = shutil.which(configured)
        if found is None:
            raise ValueError(f"{name} executable unavailable")
        resolved = Path(found)
    return {"name": name, "sha256": _file_fingerprint(resolved)}


def _native_frames_proof(
    frames: Sequence[NativeSourceFrame],
    requested: tuple[Fraction, Fraction],
    source_sha256: str,
    max_png_bytes: int,
) -> dict[str, Any]:
    if not frames:
        raise ValueError("bounded native window decoded no source frames")
    first = frames[0]
    if any(
        frame.source_epoch != first.source_epoch
        or frame.source_video_sha256 != source_sha256
        or frame.time_base != first.time_base
        or (frame.width, frame.height) != (first.width, first.height)
        for frame in frames
    ):
        raise ValueError("native window mixed decoder epoch, source, or geometry")

    retained_bytes = 0
    selected: list[NativeSourceFrame] = []
    digest = hashlib.sha256()
    for frame in frames:
        frame.read_image()
        retained_bytes += frame.path.stat().st_size
        if retained_bytes > max_png_bytes:
            raise ValueError("native PNG storage budget exceeded")
        pts = frame.pts_ticks * frame.time_base
        if requested[0] <= pts <= requested[1]:
            selected.append(frame)
            digest.update(json.dumps(
                [frame.pts_ticks, frame.time_base.numerator, frame.time_base.denominator,
                 frame.pixel_sha256], separators=(",", ":"),
            ).encode("ascii"))
    if not selected:
        raise ValueError("requested rational window contains no native source PTS")
    return {
        "requested_window_rational": [str(requested[0]), str(requested[1])],
        "decode_window_sec": None,
        "verified_native_frames": len(frames),
        "selected_native_frames": len(selected),
        "selected_first_pts": [selected[0].pts_ticks, str(selected[0].time_base)],
        "selected_last_pts": [selected[-1].pts_ticks, str(selected[-1].time_base)],
        "native_pts_pixel_sequence_sha256": digest.hexdigest(),
        "source_epoch": first.source_epoch,
        "retained_png_bytes": retained_bytes,
        "max_png_bytes": max_png_bytes,
        "source_terminal_verified": True,
    }


def inspect_windows(
    video: Path,
    source_sha256: str,
    windows: Sequence[tuple[Fraction, Fraction]],
    *,
    max_png_bytes: int,
    timeout_sec: float = 1800,
    service: VideoService | None = None,
) -> dict[str, Any]:
    """Verify isolated windows using the production native decoder contract."""
    validate_windows(windows, max_png_bytes)
    if len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ValueError("lowercase source SHA256 required")
    if type(timeout_sec) not in (int, float) or not math.isfinite(timeout_sec) or timeout_sec <= 0:
        raise ValueError("positive finite decoder timeout required")
    video = video.expanduser().resolve()
    service = service or VideoService(timeout_sec=timeout_sec, pts_timeout_sec=timeout_sec)
    implementation_hashes = {
        "diagnostic": _file_fingerprint(Path(__file__)),
        "native_decoder": _file_fingerprint(Path(native_module.__file__)),
        "video_service": _file_fingerprint(Path(service_module.__file__)),
    }
    tools = [
        _tool_fingerprint(service, "ffprobe", service.ffprobe_path),
        _tool_fingerprint(service, "ffmpeg", service.ffmpeg_path or "ffmpeg"),
    ]
    started = time.monotonic()
    if _sha256(video) != source_sha256:
        raise ValueError("source video SHA256 mismatch")

    proofs = []
    peak_retained_bytes = 0
    for requested in windows:
        begin, end = requested
        decode_begin = max(0.0, math.nextafter(float(begin), -math.inf))
        if "e" in str(decode_begin).lower():
            decode_begin = float(int(decode_begin))
        decode_end = math.nextafter(float(end), math.inf)
        with service.native_window(
            video, start_sec=decode_begin, end_sec=decode_end,
            source_video_sha256=source_sha256, png_prediction="up",
            max_png_bytes=max_png_bytes,
        ) as frames:
            proof = _native_frames_proof(frames, requested, source_sha256, max_png_bytes)
            proof["decode_window_sec"] = [decode_begin, decode_end]
            peak_retained_bytes = max(peak_retained_bytes, proof["retained_png_bytes"])
        proofs.append(proof)

    if _sha256(video) != source_sha256:
        raise ValueError("source video changed during bounded inspection")
    if implementation_hashes != {
        "diagnostic": _file_fingerprint(Path(__file__)),
        "native_decoder": _file_fingerprint(Path(native_module.__file__)),
        "video_service": _file_fingerprint(Path(service_module.__file__)),
    }:
        raise ValueError("decoder implementation changed during bounded inspection")
    if tools != [
        _tool_fingerprint(service, "ffprobe", service.ffprobe_path),
        _tool_fingerprint(service, "ffmpeg", service.ffmpeg_path or "ffmpeg"),
    ]:
        raise ValueError("decoder tools changed during bounded inspection")
    return {
        "schema_version": 1,
        "scope": "bounded_native_source_pts_pixel_windows_only",
        "source_video_sha256": source_sha256,
        "implementation_sha256": implementation_hashes,
        "decoder_tools": tools,
        "windows": proofs,
        "max_window_png_bytes": max_png_bytes,
        "peak_retained_png_bytes": peak_retained_bytes,
        "source_terminal_verified": True,
        "whole_source_pts_pixels_verified": False,
        "cross_window_continuity_asserted": False,
        "recognition_executed": False,
        "qualification_established": False,
        "elapsed_sec": time.monotonic() - started,
    }


def parse_window(text: str) -> tuple[Fraction, Fraction]:
    try:
        parts = text.split(":")
        if len(parts) != 2:
            raise ValueError
        begin, end = (Fraction(part) for part in parts)
    except (ValueError, ZeroDivisionError) as error:
        raise argparse.ArgumentTypeError("window must be rational START:END seconds") from error
    if not 0 <= begin < end:
        raise argparse.ArgumentTypeError("window requires 0 <= START < END")
    return begin, end


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--window", type=parse_window, action="append", required=True)
    parser.add_argument("--max-png-bytes", type=int, required=True)
    parser.add_argument("--timeout-sec", type=float, default=1800)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    validate_windows(args.window, args.max_png_bytes)
    if args.output.exists():
        raise ValueError("output receipt already exists")
    report = inspect_windows(
        args.video, args.source_sha256, args.window,
        max_png_bytes=args.max_png_bytes, timeout_sec=args.timeout_sec,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scope": report["scope"], "windows": len(report["windows"]),
                      "source_terminal_verified": True,
                      "whole_source_pts_pixels_verified": False}))


if __name__ == "__main__":
    main()
