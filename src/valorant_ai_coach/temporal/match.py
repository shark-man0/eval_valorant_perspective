"""Development-only whole-recording timeline CLI with adaptive native sampling.

Source identity is used for admission/provenance only. The observer sees pixels
without timestamps, Source identity, labels, roster, or an initialized state.
Frames stream through a bounded buffer; original PTS and pixel hashes survive.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import struct
import subprocess
import time
import uuid
from collections.abc import Iterator
from fractions import Fraction
from pathlib import Path
from typing import IO, Any, cast

import cv2
import numpy as np

from valorant_ai_coach.video.native import _sha256, decoded_source_ticks
from valorant_ai_coach.video.service import _subprocess_environment

from .evidence import digest, freeze_native_sample, native_time
from .game import DevelopmentGameTimeline, observation
from .match_observer import ProfileHudObserver
from .replay import SourcePolicy, file_sha, peak_rss_mib, read_json, write_private


def _read_exact(stream: IO[bytes], size: int) -> bytes:
    result = bytearray()
    while len(result) < size:
        part = stream.read(size - len(result))
        if not part:
            raise ValueError("Truncated native PNG stream")
        result.extend(part)
    return bytes(result)


def png_frames(stream: IO[bytes], *, max_frame_bytes: int = 64 * 1024**2) -> Iterator[bytes]:
    """Bound each encoded native frame independently; never buffer a movie."""
    while True:
        first = stream.read(1)
        if not first:
            return
        signature = first + _read_exact(stream, 7)
        if signature != b"\x89PNG\r\n\x1a\n":
            raise ValueError("Expected native PNG framing")
        encoded = bytearray(signature)
        while True:
            header = _read_exact(stream, 8)
            size = struct.unpack(">I", header[:4])[0]
            if len(encoded) + size + 12 > max_frame_bytes:
                raise ValueError("Native frame exceeds memory budget")
            encoded.extend(header)
            encoded.extend(_read_exact(stream, size + 4))
            if header[4:] == b"IEND":
                yield bytes(encoded)
                break


def refinement_windows(
    records: list[dict[str, Any]],
    *,
    max_windows: int,
    padding: Fraction = Fraction(1),
    max_total_seconds: Fraction = Fraction(240),
    origin: Fraction = Fraction(0),
) -> tuple[list[tuple[Fraction, Fraction]], int]:
    """Select from observed changes only; no known Round times or Source cases."""
    windows: list[tuple[Fraction, Fraction]] = []
    for before, after in zip(records, records[1:], strict=False):
        a, b = before["measurement"], after["measurement"]
        clocks = [v["context"].get("timer_seconds") for v in (a, b)]
        changed = (
            a["signals"] != b["signals"]
            or a["context"].get("score") != b["context"].get("score")
            or bool(a.get("map_candidates")) != bool(b.get("map_candidates"))
            or all(v is not None for v in clocks)
            and abs(clocks[1] - clocks[0]) > 2
        )
        if not changed:
            continue
        lower = max(origin, native_time(before["sample"]) - padding)
        upper = native_time(after["sample"]) + padding
        if windows and lower <= windows[-1][1]:
            windows[-1] = windows[-1][0], max(upper, windows[-1][1])
        else:
            windows.append((lower, upper))
    chosen = []
    remaining = max_total_seconds
    deferred = max(0, len(windows) - max_windows)
    for lower, upper in windows[:max_windows]:
        if remaining <= 0:
            deferred += 1
            continue
        end = min(upper, lower + remaining)
        chosen.append((lower, end))
        remaining -= end - lower
        deferred += int(end < upper)
    return chosen, deferred


def run_match(
    *,
    policy_path: Path,
    source_id: str,
    reader_config: Path,
    output: Path,
    coarse_seconds: Fraction = Fraction(1),
    dense_seconds: Fraction = Fraction(1, 5),
    max_refinement_windows: int = 40,
    stop_after: int | None = None,
    retain_frames: bool = False,
) -> dict[str, Any]:
    began = time.perf_counter()
    implementation_sha = file_sha(Path(__file__))
    if not 0 < dense_seconds < coarse_seconds <= 2 or max_refinement_windows < 0:
        raise ValueError("Bounded coarse/dense observation cadence required")
    if stop_after is not None and (type(stop_after) is not int or not 0 < stop_after <= 180):
        raise ValueError("Pilot limit must be at most 180 seconds")
    output = output.expanduser().resolve()
    if output.exists() or any((p / ".git").exists() for p in output.parents):
        raise ValueError("New private output directory outside Git required")
    policy_data = read_json(policy_path)
    policy = SourcePolicy(policy_data)
    candidates = [v for v in policy.allowed.values() if v["video_id"] == source_id]
    if len(candidates) != 1:
        raise ValueError("Registered, explicitly admitted DEVELOPMENT source required")
    source = candidates[0]
    video = Path(source["managed_path"])
    if _sha256(video) != source["source_sha256"]:
        raise ValueError("Source bytes changed")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("FFmpeg and ffprobe required")
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=time_base,width,height,duration,duration_ts,start_pts",
            "-of",
            "json",
            str(video),
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        env=_subprocess_environment(),
    )
    stream = json.loads(proc.stdout)["streams"][0]
    base = Fraction(stream["time_base"])
    duration = int(stream["duration_ts"]) * base
    native_start = int(stream["start_pts"]) * base
    if base <= 0 or duration <= 0:
        raise ValueError("Native stream timing required")
    limit = min(duration, Fraction(stop_after)) if stop_after is not None else duration
    observer = ProfileHudObserver(reader_config)
    epoch = uuid.uuid4().hex
    output.mkdir(parents=True, mode=0o700)
    records: dict[int, dict[str, Any]] = {}

    def decode(lower: Fraction, upper: Fraction, step: Fraction, name: str) -> None:
        tick_lower, tick_upper = math.ceil(lower / base), math.floor(upper / base)
        filters = (
            f"trim=end_pts={tick_upper + 1},select=between(pts\\,{tick_lower}\\,{tick_upper}),"
            f"select=isnan(prev_selected_pts)+gte(t-prev_selected_t\\,{float(step)}),"
            "showinfo"
        )
        command = [ffmpeg, "-hide_banner", "-loglevel", "info", "-threads", "1"]
        if lower > 0:
            command += ["-noaccurate_seek", "-seek_timestamp", "1", "-ss", str(float(lower))]
        command += [
            "-copyts",
            "-i",
            str(video),
            "-an",
            "-sn",
            "-dn",
            "-map",
            "0:v:0",
            "-t",
            str(float(upper + 1)),
            "-vf",
            filters,
            "-fps_mode",
            "passthrough",
            "-threads",
            "1",
            "-c:v",
            "png",
            "-compression_level",
            "1",
            "-pred",
            "up",
            "-f",
            "image2pipe",
            "pipe:1",
        ]
        log_path = output / f"{name}_decode.log"
        pending: list[dict[str, Any]] = []
        with log_path.open("x", encoding="utf-8") as log:
            child = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=log, env=_subprocess_environment()
            )
            assert child.stdout is not None
            try:
                for encoded in png_frames(child.stdout):
                    image = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if image is None or [image.shape[1], image.shape[0]] != [
                        int(stream["width"]),
                        int(stream["height"]),
                    ]:
                        raise ValueError("Native decoded geometry mismatch")
                    measurement = observer.inspect(cast(np.typing.NDArray[np.uint8], image))
                    item = {
                        "encoded_sha": hashlib.sha256(encoded).hexdigest(),
                        "pixel_sha": hashlib.sha256(image.tobytes()).hexdigest(),
                        "measurement": measurement,
                    }
                    if retain_frames:
                        path = output / f"{name}_{len(pending):06d}.png"
                        path.write_bytes(encoded)
                        path.chmod(0o600)
                        item["path"] = str(path)
                    pending.append(item)
                    if len(pending) % 60 == 0:
                        print(
                            json.dumps(
                                {
                                    "pass": name,
                                    "observed": len(pending),
                                    "elapsed_sec": time.perf_counter() - began,
                                }
                            ),
                            flush=True,
                        )
                if child.wait(timeout=60) != 0:
                    raise ValueError("Decoder did not complete successfully; inspect private log")
            finally:
                child.stdout.close()
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=60)
        ticks = decoded_source_ticks(log_path.read_text(encoding="utf-8"), base)
        if (
            len(ticks) != len(pending)
            or not ticks
            or any(not tick_lower <= t <= tick_upper for t in ticks)
            or any(b <= a for a, b in zip(ticks, ticks[1:], strict=False))
        ):
            raise ValueError("Decoder output/native PTS correspondence failed")
        for tick, item in zip(ticks, pending, strict=True):
            if tick in records:
                if records[tick]["sample"]["native_pixel_sha256"] != item["pixel_sha"]:
                    raise ValueError("Repeated decoding changed native pixels")
                continue
            sample = freeze_native_sample(
                {
                    "source_id": source_id,
                    "source_sha256": source["source_sha256"],
                    "acquisition_id": epoch,
                    "native_epoch": epoch,
                    "native_pts_tick": tick,
                    "native_time_base": str(base),
                    "frame_size_px": [int(stream["width"]), int(stream["height"])],
                    "acquired_frame_sha256": item.pop("encoded_sha"),
                    "native_pixel_sha256": item.pop("pixel_sha"),
                }
            )
            records[tick] = {"sample": sample, "pass": name, **item}

    decode(native_start, native_start + limit, coarse_seconds, "coarse")
    coarse = [records[k] for k in sorted(records)]
    windows, deferred = refinement_windows(
        coarse, max_windows=max_refinement_windows, origin=native_start
    )
    for index, (lower, upper) in enumerate(windows):
        decode(lower, min(upper, native_start + limit), dense_seconds, f"dense_{index:04d}")
    if _sha256(video) != source["source_sha256"]:
        raise ValueError("Source bytes changed during processing")
    if file_sha(Path(__file__)) != implementation_sha:
        raise ValueError("Acquisition implementation changed during execution")
    engine = DevelopmentGameTimeline(fuse_exact_native_evidence=True)
    for tick in sorted(records):
        r = records[tick]
        m = r["measurement"]
        engine.add(
            observation(
                sample=r["sample"],
                producer=observer.fingerprint,
                signals=m["signals"],
                context=m["context"],
                raw=m["raw"],
                map_candidates=m["map_candidates"],
                continuity={"decode_ok": True},
            )
        )
    timeline = engine.rebuild()
    write_private(
        output / "observations_PRIVATE.json",
        {
            "records": list(records.values()),
            "reader_bindings": observer.bindings,
            "reader_fingerprint": observer.fingerprint,
        },
    )
    write_private(output / "timeline_PRIVATE.json", timeline)
    # Seconds outside observed endpoints remain explicit unobserved rows.
    relative_bins: dict[int, list[dict[str, Any]]] = {}
    for frame in timeline["frames"]:
        second = int((native_time(frame["sample"]) - native_start) // 1)
        relative_bins.setdefault(second, []).append(frame)
    with (output / "timeline_1s_PRIVATE.csv").open("x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["source_id", "recording_second", "observation_present", "round", "life", "camera"]
        )
        for second in range(math.ceil(limit)):
            rows = relative_bins.get(second, [])
            writer.writerow(
                [
                    source_id,
                    second,
                    bool(rows),
                    *(
                        next(iter(values)) if len(values) == 1 else "UNKNOWN"
                        for d in ("round", "life", "camera")
                        for values in [{r[d]["value"] for r in rows}]
                    ),
                ]
            )
    receipt = {
        "version": "development_full_match_v1",
        "source_id": source_id,
        "source_sha256": source["source_sha256"],
        "physical_match_id": source["physical_match_id"],
        "duration_seconds": str(duration),
        "native_start_pts_tick": int(stream["start_pts"]),
        "sampling": {
            "coarse_seconds": str(coarse_seconds),
            "dense_seconds": str(dense_seconds),
            "max_refinement_windows": max_refinement_windows,
            "max_refinement_seconds": 240,
        },
        "processed_limit_seconds": str(limit),
        "whole_file_completed": stop_after is None,
        "source_bytes_verified_before_and_after": True,
        "policy_sha256": file_sha(policy_path),
        "reader_fingerprint": observer.fingerprint,
        "implementation_sha256": implementation_sha,
        "shared_engine_sha256": file_sha(Path(__file__).with_name("game.py")),
        "decoder_binary_sha256s": {
            "ffmpeg": file_sha(Path(ffmpeg)),
            "ffprobe": file_sha(Path(ffprobe)),
        },
        "all_decoded_frame_PTS_audited": False,
        "epoch": epoch,
        "coarse_points": len(coarse),
        "observed_native_points": len(records),
        "refinement_windows": [[str(a), str(b)] for a, b in windows],
        "deferred_refinement_windows": deferred,
        "elapsed_seconds": time.perf_counter() - began,
        "python_peak_RSS_MiB": peak_rss_mib(),
        "semantic_continuity": "UNKNOWN",
        "native_frame_PTS_retained": True,
        "formal_outputs": 0,
        "map_reader_status": "UNCONFIGURED",
        "recognition_accuracy": None,
        "artifact_sha256s": {
            name: file_sha(output / name)
            for name in (
                "observations_PRIVATE.json",
                "timeline_PRIVATE.json",
                "timeline_1s_PRIVATE.csv",
            )
        },
    }
    receipt["receipt_id"] = digest(receipt)
    write_private(output / "completion_PRIVATE.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--reader-config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-refinement-windows", type=int, default=40)
    parser.add_argument("--pilot-seconds", type=int)
    parser.add_argument("--retain-frames", action="store_true")
    args = parser.parse_args()
    result = run_match(
        policy_path=args.policy,
        source_id=args.source_id,
        reader_config=args.reader_config,
        output=args.output,
        max_refinement_windows=args.max_refinement_windows,
        stop_after=args.pilot_seconds,
        retain_frames=args.retain_frames,
    )
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
