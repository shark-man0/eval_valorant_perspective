"""Resumable bit-exact decode of canonical samples into YUV minimap crops (development only).

For recordings whose timeline was acquired on another platform. The H.264 decode is
bit-exact everywhere; only the conversion to RGB differs between FFmpeg builds. Each
native audit batch writes the yuv420p crop (the minimap ROI plus a 16 px margin, even
aligned) of every requested sample. ``convert_yuv.py`` converts the crops where the
timeline was acquired and checks them against the minimap hash the timeline recorded.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import zlib
from multiprocessing import Process
from pathlib import Path
from typing import Any

import numpy as np

from valorant_ai_coach.temporal.camera_panel import NATIVE_TIME_BASE, native_decode_command
from valorant_ai_coach.temporal.match import _native_audit_batches
from valorant_ai_coach.video.native import decoded_source_ticks
from valorant_ai_coach.video.service import _subprocess_environment

WIDTH, HEIGHT = 1920, 1080
X0, Y0, X1, Y1 = 4, 32, 492, 492  # ROI (20, 48, 475, 475) with a 16 px margin
FRAME_BYTES = WIDTH * HEIGHT * 3 // 2


def batches(job: dict[str, Any]) -> list[tuple[list[int], list[dict[str, Any]]]]:
    by_tick: dict[int, list[dict[str, Any]]] = {}
    for frame in job["native_frames"].values():
        sample = frame["sample"]
        by_tick.setdefault(int(sample["native_pts_tick"]), []).append(sample)
    return [(ticks, [s for t in ticks for s in by_tick[t]])
            for ticks in _native_audit_batches(sorted(by_tick), NATIVE_TIME_BASE)]


def crop(frame: bytes) -> bytes:
    size = WIDTH * HEIGHT
    luma = np.frombuffer(frame[:size], np.uint8).reshape(HEIGHT, WIDTH)
    u = np.frombuffer(frame[size:size * 5 // 4], np.uint8).reshape(HEIGHT // 2, WIDTH // 2)
    v = np.frombuffer(frame[size * 5 // 4:], np.uint8).reshape(HEIGHT // 2, WIDTH // 2)
    return (luma[Y0:Y1, X0:X1].tobytes() + u[Y0 // 2:Y1 // 2, X0 // 2:X1 // 2].tobytes()
            + v[Y0 // 2:Y1 // 2, X0 // 2:X1 // 2].tobytes())


def _decode(video: Path, ticks: list[int], samples: list[dict[str, Any]]
            ) -> tuple[list[dict[str, Any]], bytes]:
    command = [str(video) if part == "{video}" else part
               for part in native_decode_command("ffmpeg", ticks)]
    cut = command.index("-c:v")
    command = command[:cut] + ["-pix_fmt", "yuv420p", "-f", "rawvideo", "pipe:1"]
    result = subprocess.run(command, capture_output=True, env=_subprocess_environment(),
                            check=False)
    if result.returncode:
        raise SystemExit("Native YUV decode failed")
    decoded = decoded_source_ticks(result.stderr.decode("utf-8", "replace"), NATIVE_TIME_BASE)
    if len(decoded) * FRAME_BYTES != len(result.stdout):
        raise SystemExit("Decoded frame count and PTS count differ")
    wanted = {int(s["native_pts_tick"]): s for s in samples}
    rows, blob = [], b""
    for number, tick in enumerate(decoded):
        sample = wanted.pop(tick, None)
        if sample is None:
            continue
        data = crop(result.stdout[number * FRAME_BYTES:(number + 1) * FRAME_BYTES])
        rows.append({"sample_sha256": sample["sample_sha256"], "native_pts_tick": tick,
                     "offset": len(blob), "size": len(data)})
        blob += data
    rows += [{"sample_sha256": s["sample_sha256"], "native_pts_tick": t, "missing": True}
             for t, s in wanted.items()]
    return rows, blob


def worker(job_path: Path, video: Path, out: Path, deadline: float, part: int,
           parts: int) -> None:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    for number, (ticks, samples) in enumerate(batches(job)):
        marker = out / "yuv" / f"{ticks[0]}.json"
        if number % parts != part or marker.exists():
            continue
        if time.time() > deadline:
            return
        rows, blob = _decode(video, ticks, samples)
        (out / "yuv" / f"{ticks[0]}.zz").write_bytes(zlib.compress(blob, 6))
        marker.write_text(json.dumps(rows), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job", type=Path)
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--budget-seconds", type=float, default=150)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    (args.output / "yuv").mkdir(parents=True, exist_ok=True)
    deadline = time.time() + args.budget_seconds
    processes = [Process(target=worker, args=(args.job, args.video, args.output, deadline, p,
                                              args.workers)) for p in range(args.workers)]
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    total = len(batches(json.loads(args.job.read_text(encoding="utf-8"))))
    done = len(list((args.output / "yuv").glob("*.json")))
    print(json.dumps({"batches_done": done, "batches_total": total}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
