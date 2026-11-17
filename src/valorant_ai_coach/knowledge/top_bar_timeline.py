"""Top-bar score/timer readings as shared-timeline observations.

This is the hand-off of the score recognizer to the shared timeline
(``temporal.game.DevelopmentGameTimeline``): the timeline stays the only owner
of rounds and phases, and this module only supplies evidence rows in its own
``observation`` format, the same fields its existing round readers fill
(``context.score``, ``context.timer_seconds`` and the ``active`` signal when the
clock shows more than the longest buy countdown).

Rows are development-only, unqualified claims, like every timeline supplier.
"""

from __future__ import annotations

import hashlib
from typing import Any

import cv2
import numpy as np

from ..temporal.game import observation
from .score_reader import ScoreReader

TOP_BAR_ROI = (385, 0, 1540, 100)  # 1920x1080 reference pixels
ARCHIVE_SCALE = 0.5  # the reader works on the half-scale crop
ACTIVE_CLOCK_MIN = 45  # same rule as the timeline's round readers: > 45 s is active
STREAM_KIND = "top_bar_score_timer_v1"


def reader_fingerprint(reader: ScoreReader) -> str:
    """SHA-256 of the reader's templates and rule constants (timeline producer id)."""
    digest = hashlib.sha256(STREAM_KIND.encode("ascii"))
    digest.update(np.ascontiguousarray(reader.templates, dtype=np.float32).tobytes())
    return digest.hexdigest()


def top_bar_crop(frame: np.ndarray) -> np.ndarray:
    """Half-scale top-bar crop from a full frame of any 16:9 size."""
    height, width = frame.shape[:2]
    sx, sy = width / 1920.0, height / 1080.0
    x0, y0, x1, y1 = TOP_BAR_ROI
    roi = frame[round(y0 * sy):round(y1 * sy), round(x0 * sx):round(x1 * sx)]
    size = (round((x1 - x0) * ARCHIVE_SCALE), round((y1 - y0) * ARCHIVE_SCALE))
    return cv2.resize(roi, size, interpolation=cv2.INTER_AREA)


def top_bar_observation(frame: np.ndarray, sample: dict[str, Any], reader: ScoreReader,
                        *, producer: str | None = None) -> dict[str, Any]:
    """One timeline observation row for a decoded frame and its native sample."""
    crop = top_bar_crop(frame)
    reading = reader.read(crop)
    timer = reader.read_timer(crop)
    score = ([reading.ally, reading.enemy]
             if reading.ally is not None and reading.enemy is not None else None)
    signals = ["active"] if timer is not None and timer > ACTIVE_CLOCK_MIN else []
    return observation(
        sample=sample,
        producer=producer or reader_fingerprint(reader),
        signals=signals,
        raw={"ally_score": reading.ally, "enemy_score": reading.enemy, "timer": timer},
        context={"stream_kind": STREAM_KIND, "score": score, "timer_seconds": timer},
    )
