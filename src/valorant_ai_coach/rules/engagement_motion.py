"""Movement, stops and peeks around engagement starts from native-rate frames.

Input rows come from ``scripts/knowledge/extract_engagement_motion.py``: every
frame (60 fps) inside the engagement windows, with background feature motion
measured on the 480x270 view and the magazine count read on the frame.

- Shot frame: the first frame whose magazine count drops below the previous
  reading and stays there for ``CONFIRM_FRAMES`` frames. This places the first
  shot of an engagement to 1/60 s instead of the one-second keyframe interval.
- Moving: turning the view moves the whole playfield by one homography; moving
  the camera adds parallax, and moving past near cover makes background tracks
  die fast. Over ``MOVING_SPAN_SEC`` an interval is moving when the median
  homography residual over ``LAG`` frames exceeds ``MOVING_H_ERR_PX`` and the
  fewest surviving 0.2 s tracks fall below ``MOVING_MAX_TRACKS``.
- Peek: the recorder was stationary, started moving, and fired within
  ``PEEK_TO_SHOT_SEC`` of starting to move.

Review (frame strips judged by eye, 0.45 s before random times in engagement
windows): the moving rule was chosen on set A (10 of 11 moving, 0 of 20
stationary called moving) and checked on a held-out set B, where it found only
1 of 5 moving intervals (0 of 19 stationary called moving). Among first shots it
calls "moving" (256 of 1,088), a random 8 were mostly smokes, flashes and
round-end effects (1 or 2 really moving): screen-filling effects kill tracks and
raise the residual just as movement does. Movement facts and peeks therefore
stay gated off in the readiness path (``include_movement``). The first-shot
frame is the part that holds: 11 of 12 reviewed frames showed the count drop
between the frame before and the frame found.

Everything here is a development candidate (``dev-`` in the readiness path);
no state is kept and nothing is promoted. Rounds, spectating and gaps are the
shared timeline's: the caller passes only windows inside one round of own live
view.
"""

from __future__ import annotations

import json
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

LAG_SEC = 0.2
MIN_TRACKS = 40
CONFIRM_FRAMES = 3
MOVING_SPAN_SEC = 0.45
MOVING_H_ERR_PX = 0.6
MOVING_MAX_TRACKS = 60
PEEK_TO_SHOT_SEC = 1.0


@dataclass(frozen=True)
class MotionFrame:
    sec: float
    tracks: int
    lag_tracks: int
    h_err: float | None
    f_err: float | None
    dx: float | None
    dy: float | None
    magazine: int | None


def load_motion_frames(path: Path) -> list[MotionFrame]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    frames = [MotionFrame(float(r["sec"]), int(r.get("tracks", 0)), int(r.get("lag_tracks", 0)),
                          r.get("h_err"), r.get("f_err"), r.get("dx"), r.get("dy"),
                          r.get("magazine")) for r in rows]
    frames.sort(key=lambda f: f.sec)
    return frames


def between(frames: Sequence[MotionFrame], start: float, end: float) -> list[MotionFrame]:
    return [f for f in frames if start <= f.sec <= end]


def first_shot_frame(frames: Sequence[MotionFrame], start: float, end: float) -> float | None:
    """Time of the first confirmed magazine drop in ``[start, end]``."""
    window = between(frames, start - 0.5, end)
    reads = [(f.sec, f.magazine) for f in window if f.magazine is not None]
    for k in range(1, len(reads)):
        sec, value = reads[k]
        if sec < start:
            continue
        previous = reads[k - 1][1]
        assert value is not None and previous is not None
        if 0 < previous - value <= 3:
            following = [v for _, v in reads[k:k + CONFIRM_FRAMES]]
            if len(following) == CONFIRM_FRAMES and all(v == value for v in following):
                return sec
    return None


def moving_over(frames: Sequence[MotionFrame], end: float,
                span: float = MOVING_SPAN_SEC) -> bool | None:
    """True when the interval before ``end`` shows camera movement; None when
    the rule does not fire or there are too few frames (it never says
    stationary)."""
    window = between(frames, end - span, end)
    residuals = [f.h_err for f in window if f.h_err is not None]
    if len(window) < span * 60 * 0.5 or not residuals:
        return None
    if statistics.median(residuals) > MOVING_H_ERR_PX \
            and min(f.lag_tracks for f in window) < MOVING_MAX_TRACKS:
        return True
    return None


@dataclass(frozen=True)
class EngagementMotion:
    shot_sec: float  # first shot frame
    moving_before_shot: bool | None  # True, or None when not shown


def engagement_motion(frames: Sequence[MotionFrame], start: float,
                      end: float) -> EngagementMotion | None:
    """Motion before the first shot fired in ``[start, end]`` (None if no frame
    shows the drop)."""
    shot = first_shot_frame(frames, start, end)
    if shot is None:
        return None
    return EngagementMotion(shot, moving_over(frames, shot))
