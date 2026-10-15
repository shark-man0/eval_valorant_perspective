"""Fresh native-pixel identity diagnostics; no event or ownership qualification.

Selectors contain source PTS only. Outputs include private source images/signals
and must remain local. Isolated measurements do not reproduce temporal context.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path

from valorant_ai_coach.hud.analyzers import RealHudAnalyzer
from valorant_ai_coach.hud.global_lifecycle import (
    GlobalLifecycleQualification,
    global_recognizer_fingerprint,
)
from valorant_ai_coach.hud.unedited_input import UneditedInputContract
from valorant_ai_coach.video.native import decode_native_window


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "profile", "templates", "input-contract",
                 "reservation", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--qualification", type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("preserve previous evidence: output already exists")
    reservation = json.loads(args.reservation.read_text(encoding="utf-8"))
    source_hash = reservation["source_sha256"]
    if digest(args.video) != source_hash:
        parser.error("source integrity mismatch")
    paths = [args.profile, args.templates, args.input_contract, args.reservation, Path(__file__)]
    if args.qualification is not None:
        paths.append(args.qualification)
    inputs = {str(p): digest(p) for p in paths}
    code = global_recognizer_fingerprint()
    contract = UneditedInputContract.load(args.input_contract, source_video_sha256=source_hash)
    args.output.mkdir(parents=True)
    rows = []
    started = time.monotonic()
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        parser.error("ffmpeg and ffprobe are required")
    options = dict(source_video_sha256=source_hash, ffmpeg=ffmpeg, ffprobe=ffprobe)
    with decode_native_window(args.video, start_sec=0, end_sec=.09, **options) as prefix:
        for index, target in enumerate(reservation["targets"]):
            timestamp = float(target["source_pts_sec"])
            measured = []
            analyzer = RealHudAnalyzer(
                args.profile, template_profile_path=args.templates,
                global_qualification_path=(
                    args.qualification or args.output / "absent-global-qualification.json"
                ),
                diagnostic_sink=measured.append,
            )
            # The default sampled loader deliberately rejects source-assured
            # native UI components. Validate through the explicit input contract;
            # never install that qualification as sampled runtime authority.
            if args.qualification is not None:
                GlobalLifecycleQualification.load(
                    args.qualification, analyzer._base_fingerprint(),
                    unedited_input_contract=contract,
                )
            with decode_native_window(args.video, start_sec=max(0, timestamp-.02),
                                      end_sec=timestamp+.02, **options) as decoded:
                frame = min(decoded, key=lambda f: abs(f.time_sec-timestamp))
                if abs(frame.time_sec-timestamp) > .00001:
                    raise ValueError("selector does not resolve an actual native PTS")
                # The prefix initializes only geometry under the explicit input
                # contract. It supplies no phase, value, identity or history.
                analyzer.observe_native_system_frames(
                    (frame,), native_step_ticks=reservation["native_step_ticks"],
                    calibration_prefix=prefix[0],
                    input_contract_path=args.input_contract,
                )
                if len(measured) != 1:
                    raise ValueError("source diagnostic count mismatch")
                frame.read_image()
                saved = args.output / f"source_{index:03d}.png"
                shutil.copyfile(frame.path, saved)
                rows.append({
                    "selector_id": target["id"], "role": target["role"],
                    "source_pts_ticks": frame.pts_ticks, "source_time_base": str(frame.time_base),
                    "source_pts_sec": frame.time_sec,
                    "source_pixel_sha256": frame.pixel_sha256,
                    "image_path": str(saved), "image_sha256": digest(saved),
                    "profile_fingerprint": analyzer._base_fingerprint(),
                    "diagnostic": measured[0],
                })
    if (global_recognizer_fingerprint() != code or digest(args.video) != source_hash
            or any(digest(Path(p)) != value for p, value in inputs.items())):
        raise ValueError("terminal source/code/asset mismatch")
    report = {
        "scope": "Isolated current-frame source diagnostics; no temporal qualification",
        "source_sha256": source_hash, "recognizer_fingerprint": code,
        "input_sha256": inputs, "rows": rows, "wall_sec": time.monotonic()-started,
        "released_events": 0, "new_qualification": False,
        "global_qualification_verified_only": args.qualification is not None,
        "global_qualification_installed": False,
        "terminal_hashes_verified": True,
    }
    (args.output / "result.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps({"processed_source_frames": len(rows), "wall_sec": report["wall_sec"]}))


if __name__ == "__main__":
    main()
