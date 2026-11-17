"""Per-second HUD and motion features from the original recordings (development).

Decodes only each keyframe (the recordings carry one per second) plus the two
frames after it, so a full match takes about a minute instead of a full decode.
For every keyframe it writes one JSON line with the native sample identity
(PTS tick, time base, encoded-packet and pixel SHA-256), so the rows can feed
the shared one-second timeline, and the readings of our development readers:

- top bar: alive counts, score, round timer, planted-spike indicator
- ability HUD: best agent and slot charges (who is viewed)
- kill feed entries
- weapon inventory (taller ROI than the 5 s crops): spike header score
- ammo: magazine count
- motion between the keyframe and the frames 1/60 s and 2/60 s later: sparse
  optical flow on the playfield (HUD masked), homography fit, and the parallax
  that a pure camera rotation cannot explain

The run is resumable: it appends to ``<out>/<video_id>.jsonl`` and starts after
the last written keyframe, stopping before ``--budget`` seconds so it fits a
time-limited shell. PyAV is a development-time dependency of this script only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from fractions import Fraction
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from valorant_ai_coach.knowledge import load_game_knowledge
from valorant_ai_coach.knowledge.ammo_reader import AMMO_ROI, AmmoReader
from valorant_ai_coach.knowledge.assets import ReferenceAssets
from valorant_ai_coach.knowledge.hud_abilities import AbilityHudReader
from valorant_ai_coach.knowledge.kill_feed import KillFeedReader
from valorant_ai_coach.knowledge.score_reader import ScoreReader
from valorant_ai_coach.knowledge.spike_carrier import TALL_INVENTORY_ROI, SpikeCarrierReader
from valorant_ai_coach.knowledge.top_bar import read_top_bar, spike_planted_indicator

TOP_BAR_ROI = (385, 0, 1540, 100)
ABILITY_ROI = (745, 975, 1175, 1062)
KILL_FEED_ROI = (1440, 45, 1918, 188)
KILL_FEED_SCALE = 0.75
MOTION_SIZE = (480, 270)
# Playfield mask at MOTION_SIZE: drop top bar, minimap, kill feed, bottom HUD,
# the weapon model and the centre crosshair.
MOTION_MASK_BOXES = ((0, 0, 480, 30), (0, 0, 110, 110), (350, 0, 480, 60),
                     (0, 225, 480, 270), (300, 160, 480, 270), (225, 120, 255, 150))
EXTRACTOR_VERSION = "second_features_v1"


def crop(frame: np.ndarray, roi: tuple[int, int, int, int], scale: float = 1.0) -> np.ndarray:
    height, width = frame.shape[:2]
    sx, sy = width / 1920.0, height / 1080.0
    x0, y0, x1, y1 = roi
    part = frame[round(y0 * sy):round(y1 * sy), round(x0 * sx):round(x1 * sx)]
    size = (round((x1 - x0) * scale), round((y1 - y0) * scale))
    if part.shape[1] != size[0] or part.shape[0] != size[1]:
        part = cv2.resize(part, size, interpolation=cv2.INTER_AREA)
    return part


def motion_mask() -> np.ndarray:
    mask = np.full((MOTION_SIZE[1], MOTION_SIZE[0]), 255, np.uint8)
    for x0, y0, x1, y1 in MOTION_MASK_BOXES:
        mask[y0:y1, x0:x1] = 0
    return mask


def motion_features(a: np.ndarray, b: np.ndarray, mask: np.ndarray) -> dict[str, Any]:
    ga = cv2.cvtColor(cv2.resize(a, MOTION_SIZE, interpolation=cv2.INTER_AREA),
                      cv2.COLOR_BGR2GRAY)
    gb = cv2.cvtColor(cv2.resize(b, MOTION_SIZE, interpolation=cv2.INTER_AREA),
                      cv2.COLOR_BGR2GRAY)
    points = cv2.goodFeaturesToTrack(ga, maxCorners=300, qualityLevel=0.01, minDistance=6,
                                     mask=mask)
    if points is None or len(points) < 12:
        return {"tracked": 0}
    moved, status, _ = cv2.calcOpticalFlowPyrLK(ga, gb, points, None, winSize=(15, 15),
                                                maxLevel=3)
    ok = status.reshape(-1) == 1
    p0, p1 = points.reshape(-1, 2)[ok], moved.reshape(-1, 2)[ok]
    if len(p0) < 12:
        return {"tracked": int(len(p0))}
    flow = np.linalg.norm(p1 - p0, axis=1)
    homography, inliers = cv2.findHomography(p0, p1, cv2.RANSAC, 1.5)
    if homography is None:
        return {"tracked": int(len(p0)), "flow_median": float(np.median(flow))}
    projected = cv2.perspectiveTransform(p0.reshape(-1, 1, 2), homography).reshape(-1, 2)
    residual = np.linalg.norm(projected - p1, axis=1)
    return {
        "tracked": int(len(p0)),
        "flow_median": round(float(np.median(flow)), 3),
        "flow_p90": round(float(np.percentile(flow, 90)), 3),
        "inlier_ratio": round(float(inliers.mean()), 3),
        "residual_p50": round(float(np.median(residual)), 3),
        "residual_p90": round(float(np.percentile(residual, 90)), 3),
        "translation": [round(float(homography[0, 2]), 2), round(float(homography[1, 2]), 2)],
        "scale": round(float(np.sqrt(abs(np.linalg.det(homography[:2, :2])))), 4),
    }


class Readers:
    def __init__(self, cache: Path) -> None:
        knowledge = load_game_knowledge()
        assets = ReferenceAssets.load(cache)
        self.names = {a.uuid: a.name for a in knowledge.agents}
        self.hud = AbilityHudReader(knowledge, assets)
        self.feed = KillFeedReader(knowledge, assets)
        self.score = ScoreReader.load(cache)
        self.spike = SpikeCarrierReader.load(cache)
        self.ammo = AmmoReader.load(cache)
        self.mask = motion_mask()

    def read(self, frame: np.ndarray, after: list[np.ndarray]) -> dict[str, Any]:
        bar = crop(frame, TOP_BAR_ROI, 0.5)
        top = read_top_bar(bar)
        score = self.score.read(bar)
        hud = self.hud.read(crop(frame, ABILITY_ROI))
        best = int(np.argmax(hud.agent_scores))
        spike = self.spike.read(crop(frame, TALL_INVENTORY_ROI, 0.5),
                                roi=TALL_INVENTORY_ROI)
        record: dict[str, Any] = {
            "alive": ([top.ally.alive, top.enemy.alive] if top.consistent else [None, None]),
            "score": [score.ally, score.enemy],
            "timer": self.score.read_timer(bar),
            "planted": spike_planted_indicator(bar)[0],
            "hud": {"present": hud.hud_present, "agent": self.names.get(hud.agent_uuids[best]),
                    "agent_score": round(float(hud.agent_scores[best]), 3),
                    "charges": [round(s.charge_fraction, 3) for s in hud.slots]},
            "feed": [{"killer_team": e.killer_team, "victim_team": e.victim_team,
                      "killer": e.killer, "victim": e.victim,
                      "victim_score": round(e.victim_score, 3),
                      "recorder_victim": e.recorder_victim,
                      "recorder_killer": e.recorder_killer}
                     for e in self.feed.read(crop(frame, KILL_FEED_ROI, KILL_FEED_SCALE))],
            "spike_score": round(spike.score, 3),
            "spike_carried": spike.carried,
            "magazine": self.ammo.read(crop(frame, AMMO_ROI)).value,
        }
        record["motion"] = [motion_features(frame, later, self.mask) for later in after]
        return record


def run(video: Path, video_id: str, source_sha256: str, out: Path, readers: Readers,
        budget: float) -> dict[str, Any]:
    import av  # development-time dependency

    started = time.monotonic()
    path = out / f"{video_id}.jsonl"
    done_tick = -1
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done_tick = max(done_tick, int(json.loads(line)["sample"]["native_pts_tick"]))
    container = av.open(str(video))
    stream = container.streams.video[0]
    time_base = Fraction(stream.time_base.numerator, stream.time_base.denominator)
    epoch = f"{EXTRACTOR_VERSION}:{source_sha256[:16]}"
    if done_tick >= 0:
        container.seek(done_tick, stream=stream, backward=True)
    written = 0
    finished = True
    frame_ticks = max(1, round(1 / (float(time_base) * float(stream.average_rate or 60))))

    def flush(handle: Any, pending: dict[str, Any] | None, key: np.ndarray | None,
              followers: dict[int, np.ndarray]) -> int:
        if pending is None or key is None:
            return 0
        after = [followers[t] for t in sorted(followers)][:2]
        pending.update(readers.read(key, after))
        pending["motion_dt_ticks"] = [t - pending["sample"]["native_pts_tick"]
                                      for t in sorted(followers)][:2]
        handle.write(json.dumps(pending, ensure_ascii=False) + "\n")
        return 1

    with path.open("a", encoding="utf-8") as handle:
        pending: dict[str, Any] | None = None
        key_frame: np.ndarray | None = None
        followers: dict[int, np.ndarray] = {}
        key_tick = -1
        encoded = b""
        for packet in container.demux(stream):
            if packet.pts is None:
                continue
            if packet.is_keyframe:
                written += flush(handle, pending, key_frame, followers)
                pending, key_frame, followers = None, None, {}
                if time.monotonic() - started > budget:
                    finished = False
                    break
                if packet.pts <= done_tick:
                    key_tick = -1
                    continue
                key_tick = int(packet.pts)
                encoded = bytes(packet)
            elif key_tick < 0 or (key_frame is not None and len(followers) >= 2):
                continue  # rest of the GOP is not needed
            # Frames come out in display order, possibly delayed (B-frames): match by PTS.
            for frame in packet.decode():
                if frame.pts == key_tick and key_frame is None:
                    key_frame = frame.to_ndarray(format="bgr24")
                    pending = {
                        "sample": {
                            "source_id": video_id, "source_sha256": source_sha256,
                            "acquisition_id": epoch, "native_epoch": epoch,
                            "native_pts_tick": key_tick,
                            "native_time_base": str(time_base),
                            "acquired_frame_sha256": hashlib.sha256(encoded).hexdigest(),
                            "native_pixel_sha256": hashlib.sha256(
                                key_frame.tobytes()).hexdigest(),
                            "frame_size_px": [int(key_frame.shape[1]),
                                              int(key_frame.shape[0])],
                        },
                        "sec": round(float(key_tick * time_base), 4),
                    }
                elif (frame.pts is not None and key_tick < frame.pts <= key_tick + 2 * frame_ticks
                      and len(followers) < 2):
                    followers[int(frame.pts)] = frame.to_ndarray(format="bgr24")
        else:
            written += flush(handle, pending, key_frame, followers)
    container.close()
    return {"video_id": video_id, "written": written, "finished": finished,
            "elapsed": round(time.monotonic() - started, 1)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--videos", type=Path, required=True, help="lines: video_id=path")
    parser.add_argument("--hashes", type=Path, required=True, help="video_id -> sha256 JSON")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--budget", type=float, default=150.0)
    parser.add_argument("ids", nargs="*")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    videos = dict(line.split("=", 1) for line in
                  args.videos.read_text(encoding="utf-8").splitlines() if "=" in line)
    hashes = json.loads(args.hashes.read_text(encoding="utf-8"))
    readers = Readers(args.cache)
    started = time.monotonic()
    for video_id in args.ids or sorted(videos):
        marker = args.out / f"{video_id}.done"
        if marker.exists():
            continue
        remaining = args.budget - (time.monotonic() - started)
        if remaining < 10:
            break
        result = run(Path(videos[video_id].strip()), video_id, hashes[video_id]["sha256"],
                     args.out, readers, remaining)
        print(json.dumps(result))
        if result["finished"]:
            marker.write_text(json.dumps(result), encoding="utf-8")
        else:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
