"""Inspect every native source frame in explicit interior lifecycle windows.

This is an optimistic, reference-geometry diagnostic, not a qualified production
run. Actual configured timer/phase readers and continuity/lifecycle code are
used. No Validation Pack, expected values, round IDs or inferred cut labels enter
the simulation. No qualification report is created or installed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from dataclasses import asdict
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from valorant_ai_coach.hud.analyzers import (  # noqa: E402
    RealHudAnalyzer,
    _normalize_reader_value,
)
from valorant_ai_coach.hud.global_lifecycle import (  # noqa: E402
    GlobalLifecycleQualification,
    GlobalRoundLifecycle,
    global_recognizer_fingerprint,
)
from valorant_ai_coach.hud.models import accept_hud_value  # noqa: E402
from valorant_ai_coach.hud.semantic_text import SemanticPhaseContext  # noqa: E402
from valorant_ai_coach.hud.source_continuity import CompositeSourceContinuity  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_source_pts(log: str, time_base: Fraction) -> list[int]:
    """Keep original integer ticks, reject altered filter time bases/order."""
    bases = re.findall(r"config in time_base:\s*(\d+/\d+)", log)
    if not bases or any(Fraction(base) != time_base for base in bases):
        raise ValueError("showinfo source time base mismatch")
    frames = re.findall(r"\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:", log)
    if not frames or [int(n) for n, _ in frames] != list(range(len(frames))):
        raise ValueError("showinfo missing or unordered source frames")
    pts = [int(tick) for _, tick in frames]
    if any(b <= a for a, b in zip(pts, pts[1:], strict=False)):
        raise ValueError("source PTS must increase strictly")
    return pts


def verify_native_frames(actual: list[int], expected: list[int], count: int) -> None:
    if len(actual) < 2 or actual != expected or count != len(actual):
        raise ValueError("decoded frames differ from all native source PTS in window")


def native_pts_in_window(
    probed: list[int], time_base: Fraction, start: float, end: float,
) -> list[int]:
    # A seeked interval can end early because its duration starts at the actual
    # keyframe seek position. Matching that truncated list would prove nothing
    # about omitted tail frames. Require observed coverage on both sides.
    if (
        not probed or float(probed[0] * time_base) > start
        or float(probed[-1] * time_base) <= end
        or any(b <= a for a, b in zip(probed, probed[1:], strict=False))
    ):
        raise ValueError("probe must cover source frames before and after interior window")
    return [tick for tick in probed if start <= float(tick * time_base) <= end]


def probe_json(ffprobe: str, video: Path, arguments: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        [ffprobe, "-v", "error", "-select_streams", "v:0", *arguments,
         "-of", "json", str(video)],
        capture_output=True, text=True, check=True,
    )
    data: dict[str, Any] = json.loads(result.stdout)
    return data


def extract_window(
    ffmpeg: str, ffprobe: str, video: Path, directory: Path,
    start: float, end: float, time_base: Fraction,
) -> tuple[list[Path], list[int]]:
    directory.mkdir()
    probe = probe_json(ffprobe, video, [
        "-read_intervals", f"{start}%{end + 1.0}", "-show_frames",
        "-show_entries", "frame=best_effort_timestamp",
    ])
    expected = native_pts_in_window(
        [int(frame["best_effort_timestamp"]) for frame in probe["frames"]],
        time_base, start, end,
    )
    if len(expected) < 2:
        raise ValueError("native window must contain at least two source frames")
    log_path = directory / "decode.log"
    with log_path.open("w", encoding="utf-8") as log:
        subprocess.run([
            ffmpeg, "-hide_banner", "-loglevel", "info", "-threads", "1",
            "-noaccurate_seek", "-seek_timestamp", "1", "-ss", str(start),
            "-copyts", "-i", str(video), "-an", "-sn", "-dn",
            "-vf", f"select=between(t\\,{start}\\,{end}),showinfo",
            "-frames:v", str(len(expected)),
            "-fps_mode", "passthrough", "-threads", "1", "-compression_level", "1",
            "-start_number", "1", str(directory / "frame_%06d.png"),
        ], stdout=subprocess.DEVNULL, stderr=log, check=True)
    ticks = parse_source_pts(log_path.read_text(encoding="utf-8"), time_base)
    paths = sorted(directory.glob("frame_*.png"))
    verify_native_frames(ticks, expected, len(paths))
    return paths, ticks


def run(args: argparse.Namespace) -> dict[str, Any]:
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        raise ValueError("ffmpeg and ffprobe are required")
    source_hash = sha256_file(args.video)
    if source_hash != args.source_sha256:
        raise ValueError("source video SHA256 mismatch")
    metadata = probe_json(ffprobe, args.video, [
        "-show_streams", "-show_format", "-show_entries",
        "stream=time_base,r_frame_rate,width,height:format=duration",
    ])
    stream = metadata["streams"][0]
    time_base = Fraction(stream["time_base"])
    frame_rate = Fraction(stream["r_frame_rate"])
    duration = float(metadata["format"]["duration"])
    if frame_rate <= 0 or time_base <= 0:
        raise ValueError("positive source time base/frame rate required")
    for start, end in args.window:
        if not (math.isfinite(start) and math.isfinite(end) and 0 <= start < end <= duration):
            raise ValueError("explicit finite source window required")
    analyzer = RealHudAnalyzer(args.profile)
    profile_hash = analyzer.fingerprint()
    code_hash = global_recognizer_fingerprint()
    diagnostic_hash = sha256_file(Path(__file__))
    if analyzer.template_profile is None or "round_timer" not in analyzer.readers:
        raise ValueError("complete configured timer/phase profile required")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    freeze = {
        "scope": "source diagnostics, not holdout/qualification",
        "source_video_sha256": source_hash, "profile_fingerprint": profile_hash,
        "recognizer_fingerprint": code_hash, "windows_sec": args.window,
        "diagnostic_script_sha256": diagnostic_hash,
    }
    (args.output_dir / "selection.json").write_text(json.dumps(freeze, indent=2) + "\n")
    # A test-only object exercises the contract. It is never installed in the
    # profile and cannot replace independent review/holdout/negative controls.
    qualification = GlobalLifecycleQualification(
        profile_hash, "d" * 64, frozenset({"timer", "purchase_phase", "continuity"}), code_hash,
    )
    reader = analyzer.readers["round_timer"]
    windows = []
    started = time.perf_counter()
    for index, (start, end) in enumerate(args.window):
        window_started = time.perf_counter()
        paths, ticks = extract_window(
            ffmpeg, ffprobe, args.video, args.output_dir / f"window-{index:03d}",
            start, end, time_base,
        )
        phase_context = SemanticPhaseContext()
        continuity = CompositeSourceContinuity(qualification)
        lifecycle = GlobalRoundLifecycle(qualification)
        rows, decisions = [], []
        for path, tick in zip(paths, ticks, strict=True):
            image = cv2.imread(str(path))
            if image is None or image.shape != (stream["height"], stream["width"], 3):
                raise ValueError("source image dimensions/decoding mismatch")
            pts = float(tick * time_base)
            signals = analyzer.template_profile.detect_signals(image, analyzer.layout)
            signals.update(phase_context.advance(pts, signals, geometry_valid=True))
            confirmed = signals.get("semantic_buy_phase_confirmed") is True
            x1, y1, x2, y2 = analyzer.layout.normalized_roi("round_timer").pixel_bounds(
                image.shape[1], image.shape[0],
            )
            result = reader.read(image, image[y1:y2, x1:x2])
            accepted = accept_hud_value(
                result.value, result.confidence, cross_checked=result.cross_checked,
            )
            timer = _normalize_reader_value("round_time_remaining_sec", "timer", accepted)
            observation = {
                "time_sec": pts, "primary_state": "unknown",
                "state_flags": ["buy_phase_banner"] if confirmed else [],
                "values": {"round_time_remaining_sec": timer, "buy_phase_visible": confirmed},
                "quality": {"roi_confidence": {
                    "round_timer_value": result.confidence if timer is not None else 0,
                    "center_phase_banner_semantic_text": signals.get(
                        "semantic_buy_phase_confidence", 0,
                    ) if confirmed else 0,
                }},
            }
            proof = continuity.advance(image, observation, {}, geometry_valid=True)
            decisions.extend(asdict(d) for d in lifecycle.advance(
                observation, {"global_continuity": proof},
            ))
            rows.append({
                "source_pts_ticks": tick, "time_base": str(time_base), "pts_sec": pts,
                "frame_sha256": sha256_file(path),
                "source_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                "timer_display": accepted, "timer_sec": timer,
                "timer_confidence": result.confidence, "timer_reader_sources": result.sources,
                "phase_template_confidence": signals.get("buy_phase_template_confidence"),
                "phase_confirmed": confirmed,
                "phase_source_pts": signals.get("semantic_buy_phase_source_pts"),
                "continuity_reason": continuity.last_reason,
                "continuity_proof": proof, "lifecycle_state": lifecycle.state,
                "preparation_pts": list(lifecycle.phase_pts),
            })
        windows.append({
            "window_sec": [start, end], "processed_frames": len(rows),
            "timer_accepted": sum(r["timer_sec"] is not None for r in rows),
            "timer_unknown": sum(r["timer_sec"] is None for r in rows),
            "phase_confirmed": sum(r["phase_confirmed"] for r in rows),
            "continuity_reasons": dict(Counter(r["continuity_reason"] for r in rows)),
            "lifecycle_states": dict(Counter(r["lifecycle_state"] for r in rows)),
            "simulated_decisions": decisions,
            "wall_clock_sec": time.perf_counter() - window_started, "rows": rows,
        })
    if (
        source_hash != sha256_file(args.video) or profile_hash != analyzer.fingerprint()
        or code_hash != global_recognizer_fingerprint()
        or diagnostic_hash != sha256_file(Path(__file__))
    ):
        raise ValueError("source/code/profile changed during diagnostic")
    return {
        **freeze, "scope": __doc__, "mode": "native_source_global_diagnostic",
        "geometry_valid_assumed": True, "primary_state_projected": "unknown",
        "reader_outputs_manually_reviewed": False,
        "qualification_created": False, "profile_adopted": False,
        "validation_pack_loaded": False, "full_sampler_changed": False,
        "native_pts_coverage_verified": True,
        "wall_clock_sec": time.perf_counter() - started, "windows": windows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--window", required=True, action="append", nargs=2, type=float)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    report = run(args)
    (args.output_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    for window in report["windows"]:
        print(json.dumps({key: value for key, value in window.items() if key != "rows"}))
    print(json.dumps({"wall_clock_sec": report["wall_clock_sec"]}))


if __name__ == "__main__":
    main()
