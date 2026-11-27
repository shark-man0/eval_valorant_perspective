"""Resumable pixel-exact decode of canonical samples into minimap crops (development only).

The job file lists the canonical timeline's frozen native samples to decode
(``{"source": ..., "input_sha256": ..., "native_frames": {key: {"sample": ...}}}``).
Frames are decoded with the repository's native decode (``camera_panel.decode_samples``,
the acquisition's own FFmpeg procedure). Only frames whose ``native_pixel_sha256`` equals
the sample's are cropped; the others are listed with ``pixel_identical: false``.

Each native audit batch (at most six seconds) is one unit of work: ``done/<tick>.json``
records its rows and ``crops/<sample>.png`` holds lossless minimap crops. A rerun skips
finished batches, so the job can be split into short calls. Requires FFmpeg 5.1 or later.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from multiprocessing import Process
from pathlib import Path
from typing import Any

import cv2

from valorant_ai_coach.temporal.camera_panel import NATIVE_TIME_BASE, decode_samples
from valorant_ai_coach.temporal.match import _native_audit_batches

ROI = (20, 48, 475, 475)  # minimap_normal at 1920x1080 (config/hud_layout_1080p_v3.json)


def batches(job: dict[str, Any]) -> list[tuple[list[int], list[dict[str, Any]]]]:
    by_tick: dict[int, list[dict[str, Any]]] = {}
    for frame in job["native_frames"].values():
        sample = frame["sample"]
        by_tick.setdefault(int(sample["native_pts_tick"]), []).append(sample)
    return [(ticks, [s for t in ticks for s in by_tick[t]])
            for ticks in _native_audit_batches(sorted(by_tick), NATIVE_TIME_BASE)]


def _decode_batch(video: Path, samples: list[dict[str, Any]], crops: Path) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    rows = []
    left, top, right, bottom = ROI
    for sample, image in decode_samples(video, samples, missing):
        if image.shape[:2] != (1080, 1920):
            raise SystemExit("1920x1080 frames expected")
        roi = image[top:bottom, left:right].copy()
        ok, png = cv2.imencode(".png", roi, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        if not ok:
            raise SystemExit("PNG encoding failed")
        (crops / f"{sample['sample_sha256']}.png").write_bytes(png.tobytes())
        rows.append({"sample_sha256": sample["sample_sha256"],
                     "native_pts_tick": sample["native_pts_tick"], "pixel_identical": True,
                     "roi_pixel_bounds": list(ROI),
                     "roi_pixel_sha256": hashlib.sha256(roi.tobytes()).hexdigest()})
    rows += [{"sample_sha256": s["sample_sha256"], "native_pts_tick": s["native_pts_tick"],
              "pixel_identical": False} for s in missing]
    return rows


def worker(job_path: Path, video: Path, out: Path, deadline: float, part: int,
           parts: int) -> None:
    job = json.loads(job_path.read_text(encoding="utf-8"))
    for number, (ticks, samples) in enumerate(batches(job)):
        marker = out / "done" / f"{ticks[0]}.json"
        if number % parts != part or marker.exists():
            continue
        if time.time() > deadline:
            return
        rows = _decode_batch(video, samples, out / "crops")
        marker.write_text(json.dumps(rows), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("job", type=Path)
    parser.add_argument("video", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--budget-seconds", type=float, default=150)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    (args.output / "done").mkdir(parents=True, exist_ok=True)
    (args.output / "crops").mkdir(exist_ok=True)
    deadline = time.time() + args.budget_seconds
    processes = [Process(target=worker, args=(args.job, args.video, args.output, deadline, p,
                                              args.workers)) for p in range(args.workers)]
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    total = len(batches(json.loads(args.job.read_text(encoding="utf-8"))))
    rows = [row for path in (args.output / "done").glob("*.json")
            for row in json.loads(path.read_text(encoding="utf-8"))]
    print(json.dumps({"batches_done": len(list((args.output / "done").glob("*.json"))),
                      "batches_total": total, "frames": len(rows),
                      "pixel_identical": sum(r["pixel_identical"] for r in rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
