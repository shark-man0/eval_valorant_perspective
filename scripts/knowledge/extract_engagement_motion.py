"""Native-rate (60 fps) camera-motion features inside engagement windows.

Usage:
    python scripts/knowledge/extract_engagement_motion.py \
        --windows windows.json --videos videos.txt --hashes video_hashes.json \
        --out OUT_DIR [--budget 150] VIDEO_ID...

``windows.json`` maps video_id -> [[start_sec, end_sec], ...] (engagement
windows from the per-second shot events). Every decoded frame inside a window
(the recording's native rate, 60 fps here) is reduced to 480x270 grey and
compared with the previous frame and with the frame ``LAG`` frames earlier:

- ``rot_dx`` / ``rot_dy``: median feature displacement frame to frame (px at
  480x270): turning the view (mouse) moves the whole scene together;
- ``h_err`` / ``f_err``: over ``LAG`` frames, the median residual of the best
  homography and of the best fundamental matrix fitted to background features
  tracked frame to frame (forward-backward checked LK) for ``LAG`` frames. A
  pure turn is a homography (``h_err`` stays near ``f_err``); moving the camera
  adds parallax that only the fundamental matrix explains. Screen-filling
  effects (smokes, flashes) also kill tracks and raise ``h_err``, which is why
  ``rules.engagement_motion`` keeps movement gated off (see its review).

``magazine`` is the magazine count read on every frame (TRAIN-built digit
templates), so a shot can be placed on the exact frame its round leaves the
magazine.

HUD regions (top bar, minimap, ability bar, inventory, ammo) and the
first-person weapon model are masked out so they do not count as background.

Each row keeps the native sample identity (PTS tick, time base, SHA-256 of the
encoded packet) of its frame. The run is resumable per video like
``extract_second_features.py``: rows are appended and ``<id>.done`` marks a
finished video; ``--budget`` stops cleanly so one call fits a time limit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import av
import cv2
import numpy as np

from valorant_ai_coach.knowledge.ammo_reader import AMMO_ROI, AmmoReader

WIDTH, HEIGHT = 480, 270
LAG = 12  # frames (0.2 s at 60 fps) for the parallax comparison
MAX_FEATURES = 250
STREAM_KIND = "engagement_motion_v1"


def background_mask() -> np.ndarray:
    mask = np.full((HEIGHT, WIDTH), 255, np.uint8)
    mask[:30, :] = 0  # top bar
    mask[:120, :110] = 0  # minimap
    mask[225:, :] = 0  # ability bar, health, ammo
    mask[:, 415:] = 0  # inventory column
    mask[120:, 270:] = 0  # first-person weapon model
    mask[125:145, 230:250] = 0  # crosshair
    return mask


MASK = background_mask()


def grays(frame: av.VideoFrame) -> tuple[np.ndarray, np.ndarray]:
    """Full-resolution grey (for the magazine count) and the 480x270 copy."""
    full = np.ascontiguousarray(frame.to_ndarray(format="gray"))
    return full, cv2.resize(full, (WIDTH, HEIGHT), interpolation=cv2.INTER_AREA)


def magazine(full: np.ndarray, reader: AmmoReader) -> int | None:
    height, width = full.shape[:2]
    sx, sy = width / 1920.0, height / 1080.0
    x0, y0, x1, y1 = AMMO_ROI
    crop = full[round(y0 * sy):round(y1 * sy), round(x0 * sx):round(x1 * sx)]
    if (sx, sy) != (1.0, 1.0):
        crop = cv2.resize(crop, (x1 - x0, y1 - y0), interpolation=cv2.INTER_AREA)
    return reader.read(crop).value


def _median_residual(src: np.ndarray, dst: np.ndarray, model: np.ndarray, kind: str) -> float:
    if kind == "h":
        projected = cv2.perspectiveTransform(src.reshape(-1, 1, 2), model).reshape(-1, 2)
        return float(np.median(np.linalg.norm(projected - dst, axis=1)))
    ones = np.ones((len(src), 1), np.float32)
    x1, x2 = np.hstack([src, ones]), np.hstack([dst, ones])
    fx1 = x1 @ model.T
    ftx2 = x2 @ model
    num = np.sum(x2 * fx1, axis=1) ** 2
    den = fx1[:, 0] ** 2 + fx1[:, 1] ** 2 + ftx2[:, 0] ** 2 + ftx2[:, 1] ** 2
    return float(np.median(np.sqrt(num / np.maximum(den, 1e-9))))


def _fit(src: np.ndarray, dst: np.ndarray) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if len(src) < 12:
        return out
    homography, _ = cv2.findHomography(src, dst, cv2.LMEDS)
    if homography is not None:
        out["h_err"] = round(_median_residual(src, dst, homography, "h"), 4)
    fundamental, _ = cv2.findFundamentalMat(src, dst, cv2.FM_LMEDS)
    if fundamental is not None and fundamental.shape == (3, 3):
        out["f_err"] = round(_median_residual(src, dst, fundamental.astype(np.float32), "f"), 4)
    return out


class Tracker:
    """Background feature tracks chained frame to frame (LK), so positions
    ``LAG`` frames apart are known even while the view turns fast."""

    def __init__(self) -> None:
        self.previous: np.ndarray | None = None
        self.tracks = np.empty((0, LAG + 1, 2), np.float32)  # oldest .. newest
        self.age = np.empty((0,), np.int32)

    def step(self, gray: np.ndarray) -> dict[str, Any]:
        out: dict[str, Any] = {"tracks": 0}
        if self.previous is not None and len(self.tracks):
            last = np.ascontiguousarray(self.tracks[:, -1].reshape(-1, 1, 2), dtype=np.float32)
            moved, status, _ = cv2.calcOpticalFlowPyrLK(self.previous, gray, last, None,
                                                        winSize=(15, 15), maxLevel=3)
            back, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, self.previous, moved, None,
                                                            winSize=(15, 15), maxLevel=3)
            moved = moved.reshape(-1, 2)
            good = ((status.reshape(-1) == 1) & (back_status.reshape(-1) == 1)
                    & (np.linalg.norm(back.reshape(-1, 2) - last.reshape(-1, 2), axis=1) < 1.0)
                    & (moved[:, 0] >= 0) & (moved[:, 0] < WIDTH)
                    & (moved[:, 1] >= 0) & (moved[:, 1] < HEIGHT))
            inside = np.zeros(len(moved), bool)
            xs, ys = moved[:, 0].astype(int), moved[:, 1].astype(int)
            valid = good.copy()
            inside[valid] = MASK[ys[valid], xs[valid]] > 0
            keep = good & inside
            steps = moved[keep] - self.tracks[keep, -1]
            out["tracks"] = int(keep.sum())
            if len(steps) >= 12:
                shift = np.median(steps, axis=0)
                out["dx"], out["dy"] = round(float(shift[0]), 3), round(float(shift[1]), 3)
            self.tracks = np.concatenate([self.tracks[keep, 1:], moved[keep, None, :]], axis=1)
            self.age = self.age[keep] + 1
            mature = self.age >= LAG
            out["lag_tracks"] = int(mature.sum())
            out.update(_fit(self.tracks[mature, 0], self.tracks[mature, -1]))
        if len(self.tracks) < MAX_FEATURES // 2:
            mask = MASK.copy()
            for x, y in self.tracks[:, -1]:
                cv2.circle(mask, (int(x), int(y)), 6, 0, -1)
            fresh = cv2.goodFeaturesToTrack(gray, MAX_FEATURES - len(self.tracks), 0.01, 6,
                                            mask=mask)
            if fresh is not None:
                fresh = fresh.reshape(-1, 2).astype(np.float32)
                block = np.repeat(fresh[:, None, :], LAG + 1, axis=1)
                self.tracks = np.concatenate([self.tracks, block], axis=0)
                self.age = np.concatenate([self.age, np.zeros(len(fresh), np.int32)])
        self.previous = gray
        return out


def run(video: Path, video_id: str, source_sha256: str, windows: list[list[float]],
        out: Path, budget: float, reader: AmmoReader) -> dict[str, Any]:
    rows_path, done_path = out / f"{video_id}.jsonl", out / f"{video_id}.done"
    if done_path.exists():
        return {"video_id": video_id, "finished": True, "written": 0}
    last_written = -1.0
    if rows_path.exists():
        for line in rows_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                last_written = max(last_written, json.loads(line)["sec"])
    started = time.monotonic()
    written = 0
    epoch = f"{STREAM_KIND}:{source_sha256[:16]}"
    open_container = av.open  # binary video container, not text
    with open(video, "rb") as handle, open_container(handle) as container, \
            rows_path.open("a", encoding="utf-8") as sink:
        stream = container.streams.video[0]
        base = stream.time_base
        assert base is not None
        for start, end in sorted(windows):
            if end <= last_written:
                continue
            begin = max(start, last_written + 1e-6)
            container.seek(int(max(begin - 1.0, 0) / base), stream=stream, backward=True)
            tracker = Tracker()
            for packet in container.demux(stream):
                if packet.pts is None:
                    continue
                digest = hashlib.sha256(bytes(packet)).hexdigest()
                decode_video_packet = packet.decode  # binary video frames, not text
                for frame in decode_video_packet():
                    sec = float(frame.pts * base)
                    if sec < begin - LAG / 60.0:
                        continue
                    full, small = grays(frame)
                    features = tracker.step(small)
                    if sec < begin or sec > end:
                        continue
                    row: dict[str, Any] = {
                        "sample": {"source_id": video_id, "source_sha256": source_sha256,
                                   "acquisition_id": epoch, "native_epoch": epoch,
                                   "native_pts_tick": int(frame.pts),
                                   "native_time_base": f"{base.numerator}/{base.denominator}",
                                   "acquired_frame_sha256": digest},
                        "sec": round(sec, 4)}
                    row.update(features)
                    row["magazine"] = magazine(full, reader)
                    sink.write(json.dumps(row) + "\n")
                    written += 1
                if float((packet.pts or 0) * base) > end + 0.1:
                    break
            sink.flush()
            last_written = end
            if time.monotonic() - started > budget:
                return {"video_id": video_id, "finished": False, "written": written}
    done_path.write_text("ok\n", encoding="utf-8")
    return {"video_id": video_id, "finished": True, "written": written}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--hashes", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--budget", type=float, default=150.0)
    parser.add_argument("--cache", type=Path, required=True,
                        help="knowledge cache with the TRAIN-built magazine digit templates")
    parser.add_argument("video_ids", nargs="+")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    windows = json.loads(args.windows.read_text(encoding="utf-8"))
    videos = dict(line.strip().split("=", 1)
                  for line in args.videos.read_text(encoding="utf-8").splitlines() if "=" in line)
    hashes = json.loads(args.hashes.read_text(encoding="utf-8"))
    reader = AmmoReader.load(args.cache)
    started = time.monotonic()
    for video_id in args.video_ids:
        remaining = args.budget - (time.monotonic() - started)
        if remaining <= 5:
            break
        result = run(Path(videos[video_id]), video_id, hashes[video_id]["sha256"],
                     windows.get(video_id, []), args.out, remaining, reader)
        print(json.dumps(result), flush=True)
        if not result["finished"]:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
