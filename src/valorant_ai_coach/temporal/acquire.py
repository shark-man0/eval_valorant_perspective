"""Bounded DEVELOPMENT acquisition: verify all native PTS, retain sparse PNGs.

The common temporal display cadence is not a decoder/continuity qualification.
The existing native decoder transport and exact PTS parser are reused unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import uuid
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import cv2

from valorant_ai_coach.video.native import (
    _decode_budgeted_pngs,
    _sha256,
    decoded_source_ticks,
)
from valorant_ai_coach.video.service import _subprocess_environment

from .evidence import freeze_native_sample
from .replay import SourcePolicy, file_sha, read_json, write_private


def acquire(
    *,
    policy_path: Path,
    source_id: str,
    start: int,
    end: int,
    output: Path,
    max_png_bytes: int = 512 * 1024**2,
) -> dict[str, Any]:
    output = output.expanduser().resolve()
    if type(start) is not int or type(end) is not int or start < 0 or not 0 < end - start <= 180:
        raise ValueError("Explicit development window of at most 180 seconds required")
    if output.exists() or any((p / ".git").exists() for p in output.resolve().parents):
        raise ValueError("New private directory outside Git required")
    policy = SourcePolicy(read_json(policy_path))
    selected_source = [r for r in policy.allowed.values() if r["video_id"] == source_id]
    if len(selected_source) != 1:
        raise ValueError("Exact allowlisted DEVELOPMENT source required")
    source = selected_source[0]
    video = Path(source["managed_path"])
    if _sha256(video) != source["source_sha256"]:
        raise ValueError("Source bytes changed before acquisition")
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise ValueError("Existing FFmpeg/ffprobe runtime required")

    def probe(arguments: list[str]) -> dict[str, Any]:
        proc = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-threads",
                "1",
                "-select_streams",
                "v:0",
                *arguments,
                "-of",
                "json",
                str(video),
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=1800,
            env=_subprocess_environment(),
        )
        value: dict[str, Any] = json.loads(proc.stdout)
        return value

    stream = probe(["-show_streams", "-show_entries", "stream=time_base,width,height"])["streams"][
        0
    ]
    base = Fraction(stream["time_base"])
    if base <= 0:
        raise ValueError("Positive source time base required")
    lower, upper = math.ceil(Fraction(start) / base), math.floor(Fraction(end) / base)
    interval = f"{'' if start <= 1 else start - 1}%{end + 1}"
    probed = tuple(
        int(f["best_effort_timestamp"])
        for f in probe(
            [
                "-read_intervals",
                interval,
                "-show_frames",
                "-show_entries",
                "frame=best_effort_timestamp",
            ]
        )["frames"]
    )
    if (
        not probed
        or probed[-1] * base <= end
        or (start > 0 and probed[0] * base > start)
        or any(b <= a for a, b in zip(probed, probed[1:], strict=False))
    ):
        raise ValueError("Native probe must cover the explicit window")
    expected = tuple(t for t in probed if lower <= t <= upper)
    step = math.ceil(Fraction(1) / base)
    retained: list[int] = []
    for tick in expected:
        if not retained or tick - retained[-1] >= step:
            retained.append(tick)
    if len(retained) < 2:
        raise ValueError("At least two native observations required")
    with TemporaryDirectory(prefix="shared-native-seconds-") as temporary:
        folder = Path(temporary)
        filters = (
            f"trim=end={end + 1},select=between(pts\\,{lower}\\,{upper}),showinfo,"
            f"select=isnan(prev_selected_pts)+gte(pts-prev_selected_pts\\,{step})"
        )
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "info",
            "-threads",
            "1",
            "-noaccurate_seek",
            "-seek_timestamp",
            "1",
            "-ss",
            str(start),
            "-copyts",
            "-i",
            str(video),
            "-an",
            "-sn",
            "-dn",
            "-map",
            "0:v:0",
            "-vf",
            filters,
            "-fps_mode",
            "passthrough",
            "-threads",
            "1",
            "-compression_level",
            "1",
            "-pred",
            "up",
            "-start_number",
            "1",
            "-c:v",
            "png",
        ]
        log_path = folder / "decode.log"
        with log_path.open("w", encoding="utf-8") as log:
            _decode_budgeted_pngs(command, folder, log, max_png_bytes, 1800)
        actual = decoded_source_ticks(log_path.read_text(encoding="utf-8"), base)
        images = sorted(folder.glob("frame_*.png"))
        if actual != expected or len(images) != len(retained):
            raise ValueError("Decoder/native PTS/sparse retention mismatch")
        if _sha256(video) != source["source_sha256"]:
            raise ValueError("Source bytes changed during acquisition")
        epoch = uuid.uuid4().hex
        records = []
        for path, tick in zip(images, retained, strict=True):
            image = cv2.imread(str(path))
            if image is None or image.shape != (int(stream["height"]), int(stream["width"]), 3):
                raise ValueError("Native sparse image geometry mismatch")
            sample = freeze_native_sample(
                {
                    "source_id": source_id,
                    "source_sha256": source["source_sha256"],
                    "acquisition_id": epoch,
                    "native_epoch": epoch,
                    "native_pts_tick": tick,
                    "native_time_base": str(base),
                    "acquired_frame_sha256": _sha256(path),
                    "native_pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
                    "frame_size_px": [int(stream["width"]), int(stream["height"])],
                }
            )
            records.append({"sample": sample, "path": str(output / path.name)})
        output.mkdir(parents=True, mode=0o700)
        for path in images:
            shutil.copyfile(path, output / path.name)
            (output / path.name).chmod(0o600)
        receipt = {
            "version": "development_sparse_native_v1",
            "frames": records,
            "all_native_pts_ticks": list(actual),
            "native_time_base": str(base),
            "window_seconds": [start, end],
            "retention_step_ticks": step,
            "policy_sha256": file_sha(policy_path),
            "implementation_sha256": file_sha(Path(__file__)),
            "source_bytes_verified_before_and_after": True,
            "semantic_continuity": "UNKNOWN",
            "sparse_points_are_not_continuous_state": True,
            "qualified": False,
            "formal_outputs": 0,
        }
        write_private(output / "acquisition.json", receipt)
        return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = acquire(
        policy_path=args.policy,
        source_id=args.source_id,
        start=args.start,
        end=args.end,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "native_decoded": len(result["all_native_pts_ticks"]),
                "retained": len(result["frames"]),
                "formal_outputs": 0,
            }
        )
    )


if __name__ == "__main__":
    main()
