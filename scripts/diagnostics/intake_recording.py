"""Source-only intake; no GT, pack, recognizer or continuity qualification."""
from __future__ import annotations

import argparse
import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path

from scripts.e2e.run_dataset_case import sha256_file, valid_id


def timeline_summary(packets: list[dict], fps: float, time_base: float) -> dict:
    """Sort presentation timestamps: decode-order reordering is not a source cut.

    Gap threshold is nominal frame interval plus two timestamp ticks. This is
    only a container timing diagnostic, never runtime continuity evidence.
    """
    if not math.isfinite(fps) or fps <= 0 or not math.isfinite(time_base) or time_base <= 0:
        raise ValueError("positive finite FPS and time base required")
    pts = []
    missing = 0
    for packet in packets:
        try:
            value = float(packet["pts_time"])
        except (KeyError, TypeError, ValueError):
            missing += 1
            continue
        if not math.isfinite(value):
            missing += 1
            continue
        pts.append(value)
    if not pts:
        raise ValueError("no usable video packet PTS")
    pts.sort()
    gaps = [after - before for before, after in zip(pts, pts[1:], strict=False)]
    limit = 1 / fps + 2 * time_base
    gap_examples = [
        {"previous_pts_sec": before, "current_pts_sec": after, "gap_sec": after - before}
        for before, after in zip(pts, pts[1:], strict=False) if after - before > limit
    ][:8]
    return {
        "packet_count": len(packets), "usable_pts_count": len(pts),
        "missing_pts_count": missing, "first_pts_sec": pts[0], "last_pts_sec": pts[-1],
        "duplicate_pts_count": sum(gap == 0 for gap in gaps),
        "max_gap_sec": max(gaps, default=0),
        "nominal_interval_sec": 1 / fps, "gap_limit_sec": limit,
        "gaps_above_nominal_count": sum(gap > limit for gap in gaps),
        "gap_examples": gap_examples,
        "order": "sorted_presentation_not_decode",
        "visual_continuity": "unverified", "unedited_source": "unverified",
    }


def inspect_recording(
    video: Path, video_id: str, ffprobe: str = "ffprobe", *, user_confirmed_unedited: bool = False,
) -> dict:
    video_id = valid_id(video_id)
    if not video.is_file():
        raise FileNotFoundError(video)
    before = sha256_file(video)
    entries = (
        "format=duration,size:stream=index,codec_type,codec_name,width,height,"
        "avg_frame_rate,time_base,duration,sample_rate,channels"
    )

    def probe(*args: str) -> dict:
        result = subprocess.run(
            [ffprobe, "-v", "error", *args, "-of", "json", str(video)],
            capture_output=True, check=True, text=True, encoding="utf-8",
        )
        if result.stderr.strip():
            raise ValueError("source probe reported errors")
        return json.loads(result.stdout)

    data = probe("-show_entries", entries)
    videos = [stream for stream in data["streams"] if stream["codec_type"] == "video"]
    if len(videos) != 1:
        raise ValueError("exactly one video stream required")
    stream = videos[0]
    duration = float(data["format"]["duration"])
    if (not math.isfinite(duration) or duration <= 0 or stream["width"] <= 0
            or stream["height"] <= 0 or int(data["format"]["size"]) != video.stat().st_size):
        raise ValueError("invalid source metadata")
    try:
        fps = float(Fraction(stream["avg_frame_rate"]))
        tick = float(Fraction(stream["time_base"]))
    except (ValueError, ZeroDivisionError, TypeError):
        raise ValueError("invalid native timing metadata") from None
    packets = probe(
        "-select_streams", "v:0", "-show_packets", "-show_entries", "packet=pts,pts_time",
    )
    timeline = timeline_summary(packets["packets"], fps, tick)
    after = sha256_file(video)
    if before != after:
        raise ValueError("source changed during intake")
    return {
        "schema_version": 1, "kind": "source_intake_not_registered_dataset",
        "video_id": video_id, "source_sha256": before,
        "source_hash_verified_after_probe": True,
        "duration_sec": duration,
        "size_bytes": int(data["format"]["size"]),
        "width": stream["width"], "height": stream["height"],
        "fps": fps, "video_codec": stream["codec_name"],
        "native_time_base": stream["time_base"],
        "native_avg_frame_rate": stream["avg_frame_rate"],
        "native_first_packet_pts": min(
            (int(p["pts"]) for p in packets["packets"] if "pts" in p), default=None,
        ),
        "audio_tracks": [
            {key: audio[key] for key in ("index", "codec_name", "sample_rate", "channels")
             if key in audio}
            for audio in data["streams"] if audio["codec_type"] == "audio"
        ],
        "timeline": timeline,
        "validation_pack": "pending_independent_annotation",
        "dataset_manifest": "pending_matching_validation_pack",
        "lifecycle_evaluation": "not_run",
        "user_declaration": {"unedited_full_match": user_confirmed_unedited},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--user-confirmed-unedited", action="store_true",
                        help="Record explicit user attestation, not machine verification")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists; intake does not overwrite reports")
    report = inspect_recording(args.video, args.video_id, args.ffprobe,
                               user_confirmed_unedited=args.user_confirmed_unedited)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
