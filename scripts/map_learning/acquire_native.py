"""Decode one admitted DEVELOPMENT recording at the first native frame in each 5 Hz bin."""

from __future__ import annotations

import argparse
import re
import subprocess
import time
from fractions import Fraction
from pathlib import Path

from valorant_ai_coach.recordings.catalog import probe_metadata
from valorant_ai_coach.temporal.replay import SourcePolicy, file_sha, read_json, write_private


def development_source(policy_path, source_sha):
    policy = SourcePolicy(read_json(policy_path))
    source = policy.allowed.get(source_sha)
    if not policy.catalog_checked or source is None or source["split"] != "DEVELOPMENT":
        raise ValueError("A catalog-admitted DEVELOPMENT recording is required")
    return policy, source


def _packet_selection(source, video: Path):
    if "intake_path" in source:
        intake_path = Path(source["intake_path"])
        if file_sha(intake_path) != source["intake_sha256"]:
            raise ValueError("Recording intake receipt changed")
        metadata = read_json(intake_path)
        if metadata["source_sha256"] != source["source_sha256"]:
            raise ValueError("Recording intake is for a different source")
    else:
        metadata = probe_metadata(video)
    raw = subprocess.check_output([
        "ffprobe", "-v", "error", "-select_streams", "v:0", "-show_packets",
        "-show_entries", "packet=pts", "-of", "csv=p=0", str(video),
    ], encoding="ascii", timeout=240)
    ticks = sorted(int(row.split(",")[0]) for row in raw.splitlines() if row.strip())
    if not ticks or len(ticks) != len(set(ticks)):
        raise ValueError("Native packet clock does not match admitted recording")
    origin = ticks[0]
    base = Fraction(metadata["native_time_base"])
    duration = Fraction(str(metadata["duration_sec"]))
    if base <= 0 or duration <= 0 or metadata.get("native_first_packet_pts", origin) != origin:
        raise ValueError("Valid native recording clock required")
    expected: dict[int, int] = {}
    for tick in ticks:
        at = (tick - origin) * base
        if 0 <= at < duration:
            expected.setdefault(int(5 * at), tick)
    if not expected:
        raise ValueError("No native frames in selected timeline span")
    return base, duration, origin, list(expected.values())


def _decoded_frames(folder: Path, base: Fraction, expected: list[int], extension: str = "png"):
    log = (folder / "decode_PRIVATE.log").read_text(encoding="utf-8", errors="replace")
    bases = re.findall(r"config in time[ _]base: (\d+/\d+)", log)
    observed = [int(tick) for tick in re.findall(r"n:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:", log)]
    files = sorted(folder.glob(f"frame_*.{extension}"))
    if (not bases or any(Fraction(value) != base for value in bases)
            or observed != expected or len(observed) != len(files)):
        raise ValueError("Decoded native timebase or 5 Hz packet selection differs")
    return [[tick, str(path)] for tick, path in zip(observed, files, strict=True)]


def acquire(
    policy_path: Path, source_sha: str, output: Path, *,
    hwaccel: str | None = None, lossless_webp: bool = False,
):
    _, source = development_source(policy_path, source_sha)
    video = Path(source["managed_path"]).resolve(strict=True)
    before = video.stat()
    if file_sha(video) != source_sha:
        raise ValueError("Exact admitted recording required")
    base, duration, origin, expected = _packet_selection(source, video)

    folder = output.resolve()
    if any((root / ".git").exists() for root in (folder, *folder.parents)):
        raise ValueError("Private video frames must remain outside Git checkouts")
    folder.mkdir(parents=True, mode=0o700, exist_ok=False)
    rate = f"(pts-({origin}))*{base.numerator * 5}/{base.denominator}"
    previous = rate.replace("pts", "prev_selected_pts", 1)
    filt = f"select='isnan(prev_selected_pts)+gt(floor({rate}),floor({previous}))',showinfo"
    started = time.monotonic()
    log_path = folder / "decode_PRIVATE.log"
    acceleration = ["-hwaccel", hwaccel] if hwaccel else []
    extension = "webp" if lossless_webp else "png"
    encoding = (["-c:v", "libwebp", "-lossless", "1", "-compression_level", "3", "-pix_fmt", "bgra"]
                if lossless_webp else ["-pix_fmt", "rgb24", "-compression_level", "1"])
    with log_path.open("xb") as log:
        subprocess.run([
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "info", "-threads", "3",
            *acceleration, "-copyts", "-i", str(video), "-an", "-sn", "-dn", "-map", "0:v:0",
            "-filter_threads", "1", "-vf", filt, "-fps_mode", "passthrough",
            "-frames:v", str(len(expected)), *encoding, "-threads", "3",
            str(folder / f"frame_%06d.{extension}"),
        ], check=True, stdout=subprocess.DEVNULL, stderr=log, timeout=7200)
    frames = _decoded_frames(folder, base, expected, extension)
    after = video.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("Original recording was modified during acquisition")
    if file_sha(video) != source_sha:
        raise ValueError("Original recording byte identity changed")
    receipt = {
        "source": source["video_id"], "sha256": source_sha, "base": str(base),
        "origin": origin, "duration": str(duration),
        "frames": frames,
        "native_pts_parity": True, "verified_source_before_after": True,
        "elapsed_decode_seconds": time.monotonic() - started,
    }
    write_private(folder / "verified_acquisition_PRIVATE.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-path", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hwaccel")
    parser.add_argument("--lossless-webp", action="store_true")
    args = parser.parse_args()
    acquire(args.policy_path, args.source_sha256, args.output,
            hwaccel=args.hwaccel, lossless_webp=args.lossless_webp)


if __name__ == "__main__":
    main()
