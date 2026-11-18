"""Round score in the top bar (ally score left of the timer, enemy score right).

The score gives the round ordinal directly (ally + enemy + 1 during a round),
which the side inference needs: counting round boundaries over- or under-counts
whenever a boundary is missed or the top bar is occluded.

Digits are matched with small grayscale templates. Riot ships no digit images,
so the templates are built by ``scripts/knowledge/build_score_templates.py``
from DEVELOPMENT recordings and kept in the private cache (never committed).

Per-frame reads are noisy (overlays, bright backgrounds); ``score_track``
keeps only reads that agree with their neighbours and with the rule that a
team's score never decreases.
"""

from __future__ import annotations

import bisect
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from numpy.typing import NDArray

# Score windows inside the archive-scale (0.5) top-bar crop, x0, y0, x1, y1.
SCORE_WINDOWS = {"ally": (203, 16, 243, 36), "enemy": (337, 16, 377, 36)}
GLYPH_SIZE = (10, 14)  # width, height after normalisation
MIN_GLYPH_HEIGHT, MAX_GLYPH_HEIGHT = 10, 14
DIGIT_MIN_SCORE = 0.75
DIGIT_MIN_MARGIN = 0.05
TEMPLATE_NAME = "score_digits_v1.npz"
MANIFEST_NAME = "score_digits_v1.json"
_TOPHAT = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))


class ScoreTemplatesUnavailable(RuntimeError):
    """The private digit templates have not been built on this machine."""


Box = tuple[int, int, int, int]


def glyph_boxes(window: np.ndarray) -> tuple[np.ndarray, list[Box]]:
    """Bright thin strokes (digits) inside a score window, left to right."""
    gray: np.ndarray = window if window.ndim == 2 else cv2.cvtColor(window, cv2.COLOR_BGR2GRAY)
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, _TOPHAT)
    mask: np.ndarray = cv2.dilate(((tophat > 40) & (gray > 150)).astype(np.uint8),
                                  np.ones((3, 1), np.uint8))
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes = []
    for index in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[index])
        if MIN_GLYPH_HEIGHT <= h <= MAX_GLYPH_HEIGHT and 1 <= w <= 9 and area >= 8:
            boxes.append((x, y, w, h))
    boxes.sort()
    return gray, boxes


def normalise_glyph(gray: np.ndarray, box: tuple[int, int, int, int]) -> NDArray[np.float32]:
    """Glyph placed on a fixed canvas: narrow digits (1) keep their width."""
    x, y, w, h = box
    glyph = gray[y:y + h, x:x + w].astype(np.float32)
    scale = GLYPH_SIZE[1] / h
    width = max(1, min(GLYPH_SIZE[0], round(w * scale)))
    resized = cv2.resize(glyph, (width, GLYPH_SIZE[1]), interpolation=cv2.INTER_AREA)
    canvas = np.full((GLYPH_SIZE[1], GLYPH_SIZE[0]), float(np.median(glyph)), np.float32)
    left = (GLYPH_SIZE[0] - width) // 2
    canvas[:, left:left + width] = resized
    canvas -= canvas.mean()
    norm = float(np.linalg.norm(canvas))
    return canvas / norm if norm > 1e-6 else canvas


# Round timer (m:ss) in the middle of the top bar, archive scale.
TIMER_WINDOW = (255, 10, 325, 40)
TIMER_MIN_HEIGHT, TIMER_MAX_HEIGHT = 10, 18
MAX_TIMER_SEC = 120
MINUTE_ONE_MIN_SCORE = 0.6


@dataclass(frozen=True)
class ScoreReading:
    ally: int | None
    enemy: int | None


class ScoreReader:
    def __init__(self, templates: NDArray[np.float32]) -> None:
        if templates.shape != (10, GLYPH_SIZE[1], GLYPH_SIZE[0]):
            raise ValueError("expected 10 digit templates")
        flat = templates.reshape(10, -1).astype(np.float32)
        flat -= flat.mean(axis=1, keepdims=True)
        flat /= np.maximum(np.linalg.norm(flat, axis=1, keepdims=True), 1e-6)
        self.templates = flat

    @classmethod
    def load(cls, cache_dir: Path) -> ScoreReader:
        path = cache_dir / "hud_templates" / TEMPLATE_NAME
        manifest = cache_dir / "hud_templates" / MANIFEST_NAME
        if not path.exists() or not manifest.exists():
            raise ScoreTemplatesUnavailable(f"missing {path}; run build_score_templates.py")
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        if meta.get("lineage", {}).get("split") != "TRAIN":
            raise ScoreTemplatesUnavailable(f"{path} has no TRAIN-only lineage; rebuild it")
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            raise ScoreTemplatesUnavailable(f"{path} does not match its manifest")
        with np.load(path) as data:
            return cls(data["digits"])

    def digit(self, glyph: NDArray[np.float32]) -> int | None:
        scores = self.templates @ glyph.reshape(-1)
        order = np.argsort(scores)[::-1]
        best, second = float(scores[order[0]]), float(scores[order[1]])
        if best < DIGIT_MIN_SCORE or best - second < DIGIT_MIN_MARGIN:
            return None
        return int(order[0])

    def read_window(self, window: np.ndarray) -> int | None:
        gray, boxes = glyph_boxes(window)
        if not 1 <= len(boxes) <= 2:
            return None
        digits = [self.digit(normalise_glyph(gray, box)) for box in boxes]
        if any(d is None for d in digits):
            return None
        return int("".join(str(d) for d in digits))

    def read_timer(self, top_bar_crop: np.ndarray) -> int | None:
        """Seconds shown by the round timer, or None (spike icon, other text).

        Expects ``m:ss``: one minute digit, a colon (two small dots), two second
        digits. Other formats (decimal countdowns, the planted-spike icon) are
        not read.
        """
        x0, y0, x1, y1 = TIMER_WINDOW
        window = top_bar_crop[y0:y1, x0:x1]
        gray: np.ndarray = window if window.ndim == 2 else cv2.cvtColor(window,
                                                                         cv2.COLOR_BGR2GRAY)
        tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, _TOPHAT)
        mask: np.ndarray = cv2.dilate(((tophat > 40) & (gray > 150)).astype(np.uint8),
                                      np.ones((3, 1), np.uint8))
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        parts: list[Box] = [(int(stats[i][0]), int(stats[i][1]), int(stats[i][2]),
                             int(stats[i][3])) for i in range(1, count)]
        digits = sorted(p for p in parts
                        if TIMER_MIN_HEIGHT <= p[3] <= TIMER_MAX_HEIGHT and p[2] <= 10)
        if len(digits) != 3:
            return None
        minute_box, tens_box, ones_box = digits
        dots = [p for p in parts if p[3] <= 6 and p[2] <= 4
                and minute_box[0] + minute_box[2] <= p[0] < tens_box[0]]
        if len(dots) < 2:
            return None
        tens = self.digit(normalise_glyph(gray, tens_box))
        ones = self.digit(normalise_glyph(gray, ones_box))
        if tens is None or ones is None or tens > 5:
            return None
        # The leading digit is only ever 0 or 1: "0" is wide, "1" narrow; a
        # middling glyph must clearly look like the "1" template.
        width = minute_box[2]
        if width >= 6:
            minute = 0
        elif width <= 4:
            minute = 1
        else:
            one = float(self.templates[1] @ normalise_glyph(gray, minute_box).reshape(-1))
            if one < MINUTE_ONE_MIN_SCORE:
                return None
            minute = 1
        value = minute * 60 + tens * 10 + ones
        return value if value <= MAX_TIMER_SEC else None

    def read(self, top_bar_crop: np.ndarray) -> ScoreReading:
        values = {}
        for side, (x0, y0, x1, y1) in SCORE_WINDOWS.items():
            values[side] = self.read_window(top_bar_crop[y0:y1, x0:x1])
        return ScoreReading(values["ally"], values["enemy"])


def score_track(reads: Sequence[tuple[float, int | None]], *, support: int = 2,
                max_score: int = 30) -> list[tuple[float, int]]:
    """Keep reads confirmed by ``support`` consecutive equal reads, then drop any
    value that would make the score decrease later (a team's score never does)."""
    values = [(sec, v) for sec, v in reads if v is not None and 0 <= v <= max_score]
    confirmed: list[tuple[float, int]] = []
    run_start = 0
    for index in range(1, len(values) + 1):
        if index == len(values) or values[index][1] != values[run_start][1]:
            if index - run_start >= support:
                confirmed.extend(values[run_start:index])
            run_start = index
    # Longest non-decreasing subsequence by value keeps the consistent reads.
    if not confirmed:
        return []
    tails: list[int] = []
    tails_idx: list[int] = []
    parent = [-1] * len(confirmed)
    for i, (_, value) in enumerate(confirmed):
        pos = bisect.bisect_right(tails, value)
        if pos == len(tails):
            tails.append(value)
            tails_idx.append(i)
        else:
            tails[pos] = value
            tails_idx[pos] = i
        parent[i] = tails_idx[pos - 1] if pos > 0 else -1
    keep = []
    i = tails_idx[-1]
    while i >= 0:
        keep.append(confirmed[i])
        i = parent[i]
    return keep[::-1]
