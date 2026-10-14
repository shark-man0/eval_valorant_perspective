"""Prepare private v3 source metadata and exact packet-PTS evidence sidecar.

Packet timestamps do not certify gameplay continuity, ownership or geometry.
No source re-encoding, Analyzer, recognizer profile or manifest registration.
"""
from __future__ import annotations

import argparse
import bisect
import json
import math
import subprocess
from fractions import Fraction
from pathlib import Path

from scripts.e2e.frame_replay import decoder_fingerprints
from scripts.e2e.run_dataset_case import sha256_file
from valorant_ai_coach.hud.calibrate_temporal import _check_output_privacy
from valorant_ai_coach.video import VideoService


def sidecar(ticks: list[int], time_base: str, bindings: list[dict], fps: float,
            source_filename: str) -> dict:
    try:
        base = Fraction(time_base)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("explicit rational packet timebase required") from exc
    if (base <= 0 or type(fps) not in (int, float) or not math.isfinite(fps) or fps <= 0
            or not ticks or any(type(t) is not int or t < 0 for t in ticks)
            or len(set(ticks)) != len(ticks)):
        raise ValueError("positive source timebase/FPS and unique explicit packet ticks required")
    ordered = sorted(ticks)
    pts = [float(t * base) for t in ordered]
    entries, seen = [], set()
    for binding in bindings:
        name = binding["evidence_path"]
        if name in seen:
            raise ValueError("duplicate evidence entry")
        seen.add(name)
        requested = binding["source_frame_pts"]
        if type(requested) not in (int, float) or not math.isfinite(requested) or requested < 0:
            raise ValueError("finite source witness PTS required")
        index = bisect.bisect_left(pts, requested)
        candidates = [i for i in (index - 1, index) if 0 <= i < len(pts)]
        nearest = min(candidates, key=lambda i: (abs(pts[i] - requested), i))
        # The extraction already supplies the decoded source frame PTS. A packet
        # sidecar may not move it to another frame merely to obtain a valid delta.
        if abs(pts[nearest] - requested) > 1e-6:
            raise ValueError("source witness is not bound to an exact packet PTS")
        delta = pts[nearest] - requested
        if abs(delta) > 1 / fps + 1e-6:
            raise ValueError("evidence exceeds canonical one-frame PTS bound")
        entries.append({"evidence_path": name, "requested_sec": requested,
                        "decoded_frame_pts_sec": round(pts[nearest], 6),
                        "presentation_index": nearest, "delta_sec": round(delta, 6),
                        "packet_pts_ticks": ordered[nearest], "time_base": str(base)})
    if not entries:
        raise ValueError("evidence sidecar cannot be empty")
    return {"version": "3.0", "timebase": "container_pts_seconds",
            "method": "nearest exact video packet PTS from ffprobe; presentation-sorted",
            "source_video": source_filename, "frame_count_indexed": len(entries),
            "max_abs_delta_sec": max(abs(e["delta_sec"]) for e in entries), "entries": entries}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("video", "intake", "point-fragments", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    _check_output_privacy(output)
    if output.exists():
        raise FileExistsError("use a new private source preparation directory")
    hashes = {p: sha256_file(p) for p in (args.intake, args.point_fragments)}
    intake = json.loads(args.intake.read_text(encoding="utf-8"))
    fragments = json.loads(args.point_fragments.read_text(encoding="utf-8"))
    source_hash = sha256_file(args.video)
    if (intake.get("source_hash_verified_after_probe") is not True
            or intake["source_sha256"] != source_hash
            or fragments["source_video_sha256"] != source_hash):
        raise ValueError("intake, evidence and current video source hashes must agree")
    ffprobe = VideoService().ffprobe_path
    probe_fingerprint, _ = decoder_fingerprints(ffprobe)

    def probe(options: list[str]) -> dict:
        result = subprocess.run([ffprobe, "-v", "error", *options, "-of", "json", str(args.video)],
                                capture_output=True, text=True, encoding="utf-8", check=True)
        return json.loads(result.stdout)

    metadata = probe(["-show_streams", "-show_format"])
    videos = [s for s in metadata["streams"] if s["codec_type"] == "video"]
    audios = [s for s in metadata["streams"] if s["codec_type"] == "audio"]
    if len(videos) != 1:
        raise ValueError("one explicit source video stream required")
    stream = videos[0]
    fps = float(Fraction(stream["avg_frame_rate"]))
    duration = float(metadata["format"]["duration"])
    if (not math.isfinite(duration) or duration <= 0
            or abs(duration - intake["duration_sec"]) > .002
            or (stream["width"], stream["height"]) != (intake["width"], intake["height"])
            or abs(fps - intake["fps"]) > 1e-6
            or len(audios) != len(intake["audio_tracks"])):
        raise ValueError("current metadata differs from the verified intake")
    for audio, recorded in zip(audios, intake["audio_tracks"], strict=True):
        if (audio["index"], audio["codec_name"], audio.get("channels")) != (
                recorded["index"], recorded["codec_name"], recorded["channels"]):
            raise ValueError("source audio stream transport metadata changed")
    packets = probe(["-select_streams", "v:0", "-show_packets", "-show_entries", "packet=pts"])
    ticks = [row["pts"] for row in packets["packets"]]
    if len(ticks) != intake["timeline"]["usable_pts_count"]:
        raise ValueError("exact packet count differs from intake")
    timeline = sidecar(ticks, stream["time_base"], fragments["evidence_bindings"], fps,
                       args.video.name)
    evidence_root = args.point_fragments.parent.resolve()
    for binding in fragments["evidence_bindings"]:
        image = (evidence_root / binding["evidence_path"]).resolve()
        if (not image.is_relative_to(evidence_root) or sha256_file(image) != binding["sha256"]):
            raise ValueError("prepared source asset integrity failed")
    if sha256_file(args.video) != source_hash or any(
        sha256_file(p) != digest for p, digest in hashes.items()
    ):
        raise ValueError("source or preparation inputs changed during probing")
    common_codec = {s["codec_name"] for s in audios}
    common_channels = {s.get("channels") for s in audios}
    common_layout = {s.get("channel_layout") for s in audios}
    if len(common_codec) != 1 or len(common_channels) != 1 or len(common_layout) != 1:
        raise ValueError("v3 transport profile requires explicitly uniform audio metadata")
    profile = {"version": "3.0", "source_filename": args.video.name, "sha256": source_hash,
               "duration_sec": duration,
               "container_start_time_sec": float(metadata["format"]["start_time"]),
               "video_stream": {"index": stream["index"], "codec": stream["codec_name"],
                                "width": stream["width"], "height": stream["height"],
                                "fps": fps, "time_base": stream["time_base"],
                                "start_time_sec": float(stream["start_time"]),
                                "duration_sec": float(stream["duration"])},
               "audio_streams": {"count": len(audios), "streams": audios,
                                 "codec": next(iter(common_codec)),
                                 "channels_each": next(iter(common_channels)),
                                 "channel_layout_each": next(iter(common_layout)),
                                 "semantic_analysis": False,
                                 "transport_expectation": "preserve all source audio tracks"},
               "timebase_policy": {"canonical": "container_pts_seconds"},
               "editing_characteristics": {
                   "visual_continuity": "not_proven_by_packet_pts",
                   "unedited_user_declaration": intake.get("user_declaration", {}).get(
                       "unedited_full_match")}}
    output.mkdir(parents=True)
    for name, value in (("source_video_profile_v3.json", profile),
                        ("frame_pts_sidecar_v3.json", timeline)):
        (output / name).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n",
                                  encoding="utf-8")
    (output / "provenance.json").write_text(json.dumps({
        "source_sha256": source_hash, "source_hash_verified_after_probe": True,
        "intake_sha256": hashes[args.intake],
        "point_fragments_sha256": hashes[args.point_fragments],
        "packet_count": len(ticks), "packet_time_base": stream["time_base"],
        "ffprobe_fingerprint": probe_fingerprint,
        "formal_pack_completed": False, "production_qualified": False,
    }, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared exact packet PTS sidecar for {len(timeline['entries'])} images; "
          "no registration")


if __name__ == "__main__":
    main()
