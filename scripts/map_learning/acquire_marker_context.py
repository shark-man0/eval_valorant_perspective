"""Retain lossless minimap crops for exact native observations in development episodes."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import cv2

from valorant_ai_coach.hud.layout import HudLayout
from valorant_ai_coach.recordings.catalog import RecordingCatalog
from valorant_ai_coach.temporal.evidence import freeze_native_sample
from valorant_ai_coach.temporal.map_view_episodes import map_view_episodes
from valorant_ai_coach.temporal.replay import file_sha, read_json, write_private

SCHEMA = "development_map_marker_context_v1"


def _ranges(ticks, clock):
    """Merge only neighboring sampled positions in the original timeline."""
    result = []
    for n, tick in enumerate(clock):
        if tick not in ticks:
            continue
        if result and result[-1][2] + 1 == n:
            result[-1] = (result[-1][0], tick, n)
        else:
            result.append((tick, tick, n))
    return [(left, right) for left, right, _ in result]


def _selection_expression(ranges):
    if len(ranges) == 1:
        lo, hi = ranges[0]
        return f"between(pts,{lo},{hi})"
    mid = len(ranges) // 2
    left = _selection_expression(ranges[:mid])
    right = _selection_expression(ranges[mid:])
    return f"if(lt(pts,{ranges[mid][0]}),{left},{right})"


def _batches(ranges, base):
    result = []
    for interval in ranges:
        if not result or (interval[0] - result[-1][-1][1]) * base > 16:
            result.append([])
        result[-1].append(interval)
    return result


def _decode_batch(video, output, bounds, origin, base, ranges, batch, hwaccel):
    span = _selection_expression(ranges)
    now = f"(pts-({int(origin)}))*{base.numerator * 5}/{base.denominator}"
    old = now.replace("pts", "prev_selected_pts", 1)
    left, top, right, bottom = bounds
    expression = (
        f"[0:v]select='isnan(prev_selected_pts)+gt(floor({now}),floor({old}))',"
        f"select='{span}',showinfo,format=bgr24,split[raw][view];"
        f"[view]crop={right - left}:{bottom - top}:{left}:{top}[roi]"
    )
    start = max(0.0, float((ranges[0][0] - int(origin)) * base) - 2)
    length = float((ranges[-1][1] - int(origin)) * base) - start + 1
    acceleration = ["-hwaccel", hwaccel] if hwaccel else []
    ffmpeg = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "info",
        "-threads",
        "2",
        *acceleration,
        "-ss",
        str(start),
        "-t",
        str(length),
        "-copyts",
        "-i",
        str(video),
        "-filter_complex_threads",
        "1",
        "-filter_complex",
        expression,
        "-map",
        "[raw]",
        "-c:v",
        "rawvideo",
        "-pix_fmt",
        "bgr24",
        "-threads",
        "1",
        "-fps_mode",
        "passthrough",
        "-f",
        "framehash",
        "-hash",
        "sha256",
        str(output / f"pixels_{batch:03d}_PRIVATE.sha256"),
        "-map",
        "[roi]",
        "-c:v",
        "png",
        "-pix_fmt",
        "rgb24",
        "-threads",
        "1",
        "-compression_level",
        "1",
        "-fps_mode",
        "passthrough",
        str(output / f"frame_{batch:03d}_%06d.png"),
    ]
    with (
        (output / f"decode_{batch:03d}_PRIVATE.log").open("xb") as log,
        subprocess.Popen(ffmpeg, stdout=subprocess.DEVNULL, stderr=log) as process,
    ):
        try:
            while process.poll() is None:
                if shutil.disk_usage(output).free < 24 * (1 << 30):
                    raise ValueError("Native context storage reserve reached")
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, ffmpeg[0])
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=20)
    log = (output / f"decode_{batch:03d}_PRIVATE.log").read_text(encoding="utf-8")
    pts = [int(v) for v in re.findall(r"\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:", log)]
    if {Fraction(x) for x in re.findall(r"config in time[ _]base: (\d+/\d+)", log)} != {base}:
        raise ValueError("Source timebase changed during exact context acquisition")
    hashes = [
        line.rsplit(",", 1)[-1].strip()
        for line in (output / f"pixels_{batch:03d}_PRIVATE.sha256")
        .read_text(encoding="ascii")
        .splitlines()
        if line and not line.startswith("#")
    ]
    crops = sorted(output.glob(f"frame_{batch:03d}_*.png"))
    if len(pts) != len(hashes) or len(pts) != len(crops) or pts != sorted(set(pts)):
        raise ValueError("Native PTS, full-image digests and ROI frames did not align")
    return list(zip(pts, hashes, crops, strict=True))


def acquire_context(
    catalog_path, recording_id, bundle, targets_path, layout_path, output, hwaccel=None
):
    catalog = RecordingCatalog(catalog_path)
    catalog.guard([recording_id], "development_analysis")
    rec = catalog.state.recordings[recording_id]
    if rec.split != "DEVELOPMENT":
        raise ValueError("Only admitted development recordings can be opened")
    timeline = read_json(bundle)
    if (
        timeline["source"]["source_sha256"] != rec.source_sha256
        or timeline["source"]["physical_match_id"] != rec.physical_match_id
        or timeline.get("formal_outputs") != 0
    ):
        raise ValueError("Timeline and recording differ")
    targets = read_json(targets_path)
    bundle_sha = file_sha(bundle)
    if targets["timeline_sha256"] != bundle_sha or targets["formal_outputs"] != 0:
        raise ValueError("Target list must be bound to the original timeline")
    target_refs = set(targets["sample_refs"])
    native = timeline["native_frames"]
    required = {
        key
        for ep in map_view_episodes(timeline)
        if target_refs.intersection(ep.current_samples)
        for key in ep.current_samples
    }
    samples = {
        item["sample_sha256"]: item
        for f in native.values()
        if (item := freeze_native_sample(f["sample"]))
    }
    if not target_refs <= samples.keys():
        raise ValueError("Unexpected sample references in context request")
    clock = sorted(s["native_pts_tick"] for s in samples.values())
    tick_rows = {samples[key]["native_pts_tick"]: samples[key] for key in required}
    if len(set(clock)) != len(clock) or len(tick_rows) != len(required):
        raise ValueError("Each native time requires exactly one input frame")
    full = {tuple(s["frame_size_px"]) for s in samples.values()}
    bases = {Fraction(s["native_time_base"]) for s in samples.values()}
    if len(full) != 1 or len(bases) != 1:
        raise ValueError("A constant raster and timebase are required")
    width, height = next(iter(full))
    base = next(iter(bases))
    layout = HudLayout.load(layout_path)
    bounds = layout.normalized_roi("minimap_normal").pixel_bounds(width, height)
    output = output.resolve()
    if any((p / ".git").exists() for p in (output, *output.parents)):
        raise ValueError("Private context cannot be written inside a Git worktree")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    index = {
        "schema": SCHEMA,
        "timeline_sha256": bundle_sha,
        "source_sha256": rec.source_sha256,
        "layout_sha256": file_sha(layout_path),
        "bounds": list(bounds),
        "frames": {},
        "requested_samples": len(required),
        "formal_outputs": 0,
    }
    if not tick_rows:
        write_private(output / "context_PRIVATE.json", index)
        return index
    video = catalog.local_path((rec.locations.get("managed") or rec.locations["original"])["path"])
    if file_sha(video) != rec.source_sha256:
        raise ValueError("Original recording bytes changed")
    before = video.stat()
    ranges = _ranges(tick_rows, clock)
    origin = Fraction(timeline["recording"]["native_origin_seconds"]) / base
    if origin.denominator != 1:
        raise ValueError("Original native origin disagrees with timebase")
    frames = index["frames"]
    for batch, group in enumerate(_batches(ranges, base)):
        for tick, pixel, crop in _decode_batch(
            video,
            output,
            bounds,
            origin,
            base,
            group,
            batch,
            hwaccel,
        ):
            sample = tick_rows.get(tick)
            if sample is None or sample["native_pixel_sha256"] != pixel:
                continue
            key = sample["sample_sha256"]
            if key in frames:
                raise ValueError("Duplicate context observation across decoder batches")
            frames[key] = {
                "file": crop.name,
                "crop_sha256": file_sha(crop),
                "native_pixel_sha256": pixel,
            }
    after = video.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Source changed during exact context acquisition")
    index["unverified_samples"] = len(required) - len(frames)
    write_private(output / "context_PRIVATE.json", index)
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("recording-catalog", "bundle", "targets", "layout", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--recording-id", required=True)
    parser.add_argument("--hwaccel")
    args = parser.parse_args()
    cv2.setNumThreads(1)
    result = acquire_context(
        args.recording_catalog,
        args.recording_id,
        args.bundle,
        args.targets,
        args.layout,
        args.output,
        args.hwaccel,
    )
    print(
        {key: result.get(key, 0) for key in ("requested_samples", "unverified_samples")}, flush=True
    )


if __name__ == "__main__":
    main()
