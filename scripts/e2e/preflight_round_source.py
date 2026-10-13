"""Source integrity and loader admission audit, never recognition qualification.

Decode only explicitly requested short windows with the production native API.
There is no GT input, recognition replay, event output or bundle generation.
Pixel checks cannot establish scene continuity or independent temporal accuracy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Sequence
from fractions import Fraction
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer  # noqa: E402
from valorant_ai_coach.hud.global_lifecycle import global_recognizer_fingerprint  # noqa: E402
from valorant_ai_coach.hud.native_assured_start import current_assured_qualification  # noqa: E402
from valorant_ai_coach.hud.unedited_input import UneditedInputContract  # noqa: E402
from valorant_ai_coach.video.native import NativeSourceFrame, _sha256, decode_native_window  # noqa: E402


def summarize_ticks(ticks: Sequence[int], time_base: Fraction) -> dict[str, Any]:
    if (len(ticks) < 2 or any(type(t) is not int or t < 0 for t in ticks)
            or time_base <= 0 or any(b <= a for a, b in zip(ticks, ticks[1:], strict=False))):
        raise ValueError("source PTS must be nonnegative integers in increasing order")
    steps = Counter(b - a for a, b in zip(ticks, ticks[1:], strict=False))
    return {
        "frame_count": len(ticks), "time_base": str(time_base),
        "first_pts_ticks": ticks[0], "last_pts_ticks": ticks[-1],
        "first_pts_sec": float(ticks[0] * time_base),
        "last_pts_sec": float(ticks[-1] * time_base),
        "step_ticks_counts": {str(k): v for k, v in sorted(steps.items())},
        "uniform_cadence": len(steps) == 1,
        "capture_loss_excluded": False,
    }


def summarize_pixels(frames: Sequence[NativeSourceFrame]) -> dict[str, Any]:
    if not frames:
        raise ValueError("nonempty decoded source window required")
    first = frames[0]
    if any((f.source_epoch, f.source_video_sha256, f.time_base, f.width, f.height)
           != (first.source_epoch, first.source_video_sha256,
               first.time_base, first.width, first.height) for f in frames):
        raise ValueError("one decoder epoch/source/geometry per window required")
    summary = summarize_ticks([f.pts_ticks for f in frames], first.time_base)
    duplicates = []
    digest = hashlib.sha256()
    retained_bytes = 0
    prior = None
    for frame in frames:
        frame.read_image()  # Check original encoded bytes and decoded pixels again.
        retained_bytes += frame.path.stat().st_size
        digest.update(json.dumps([frame.pts_ticks, str(frame.time_base), frame.pixel_sha256],
                                 separators=(",", ":")).encode("ascii") + b"\n")
        if prior is not None and frame.pixel_sha256 == prior.pixel_sha256:
            duplicates.append({"previous_pts_ticks": prior.pts_ticks,
                               "pts_ticks": frame.pts_ticks, "time_sec": frame.time_sec})
        prior = frame
    return {**summary, "source_epoch": first.source_epoch,
            "ordered_pts_pixel_sha256": digest.hexdigest(),
            "adjacent_duplicate_rasters": duplicates,
            "retained_png_bytes": retained_bytes,
            "scene_continuity_qualified": False}


def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    if _sha256(args.video) != args.source_sha256:
        raise ValueError("source video SHA256 mismatch")
    code = global_recognizer_fingerprint()
    contract = UneditedInputContract.load(args.input_contract,
                                         source_video_sha256=args.source_sha256)
    ffprobe, ffmpeg = shutil.which("ffprobe"), shutil.which("ffmpeg")
    if ffprobe is None or ffmpeg is None:
        raise ValueError("ffprobe and ffmpeg required")
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-threads", "1", "-select_streams", "v:0",
         "-show_streams", "-show_frames", "-show_entries",
         "stream=time_base,width,height:frame=best_effort_timestamp", "-of", "json",
         str(args.video)], capture_output=True, text=True, check=True, timeout=args.timeout_sec,
    )
    data = json.loads(probe.stdout)
    stream = data["streams"][0]
    time_base = Fraction(stream["time_base"])
    ticks = [int(f["best_effort_timestamp"]) for f in data["frames"]]
    report: dict[str, Any] = {
        "schema_version": "1.0", "scope": "source_preflight_and_loader_admission_only",
        "source_video_sha256": args.source_sha256,
        "recognizer_fingerprint": code, "input_contract_sha256": contract.fingerprint,
        "script_sha256": _sha256(Path(__file__)),
        "source_metadata": {**summarize_ticks(ticks, time_base),
                            "width": stream["width"], "height": stream["height"]},
        "qualification_established": False, "recognition_executed": False,
        "validation_pack_loaded": False, "windows": [],
        "profile_fingerprint": None, "qualification_sha256": None,
        "loader_admission": "not_attempted", "blockers": [],
    }
    analyzer = None
    qualification = None
    if args.profile is None or args.qualification is None:
        report["blockers"].append("current_private_profile_and_qualification_assets_required")
    else:
        analyzer = RealHudAnalyzer(args.profile, global_qualification_path=args.qualification)
        report["profile_fingerprint"] = analyzer._base_fingerprint()
        qualification = current_assured_qualification(analyzer, contract)
        report["qualification_sha256"] = qualification.report_sha256
        report["loader_admission"] = "accepted_not_temporal_qualification"
        report["components"] = sorted(qualification.components)
    report["blockers"].append("source_review_and_independent_temporal_evidence_not_evaluated")
    for start, end in args.window:
        with decode_native_window(
            args.video, start_sec=start, end_sec=end, source_video_sha256=args.source_sha256,
            ffmpeg=ffmpeg, ffprobe=ffprobe, timeout_sec=args.timeout_sec,
            png_prediction="up", max_png_bytes=args.max_png_bytes,
        ) as frames:
            window = summarize_pixels(frames)
            expected = [t for t in ticks if start <= float(t * time_base) <= end]
            if [f.pts_ticks for f in frames] != expected:
                raise ValueError("window differs from whole-source probe")
            report["windows"].append({"requested_window_sec": [start, end], **window})
    if (_sha256(args.video) != args.source_sha256 or global_recognizer_fingerprint() != code
            or UneditedInputContract.load(args.input_contract,
                                         source_video_sha256=args.source_sha256) != contract
            or (analyzer is not None
                and (analyzer._base_fingerprint() != report["profile_fingerprint"]
                     or current_assured_qualification(analyzer, contract) != qualification))):
        raise ValueError("terminal source/code/profile/qualification/contract mismatch")
    report["terminal_integrity_verified"] = True
    report["elapsed_sec"] = time.perf_counter() - started
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--input-contract", required=True, type=Path)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--qualification", type=Path)
    parser.add_argument("--window", action="append", nargs=2, type=float, default=[])
    parser.add_argument("--max-png-bytes", type=int, default=256 * 1024 * 1024)
    parser.add_argument("--timeout-sec", type=float, default=180)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if (args.profile is None) != (args.qualification is None):
        parser.error("profile and qualification must be supplied together")
    report = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"loader_admission": report["loader_admission"],
                      "qualification_established": False, "elapsed_sec": report["elapsed_sec"]}))


if __name__ == "__main__":
    main()
