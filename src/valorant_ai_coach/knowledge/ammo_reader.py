"""Magazine count in the ammo HUD (bottom centre-right), for shot detection.

A drop in the magazine count between two readings of the same weapon means
the recorder fired (the count also drops by nothing else). The large magazine
digits use a heavier face than the top-bar score, so they have their own
templates, built like the score digits (TRAIN-only, private cache, lineage in
the manifest) by ``scripts/knowledge/build_ammo_templates.py``.

The HUD shows the *viewed* player's ammo: consumers must restrict readings to
the recorder's own live view.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

AMMO_ROI = (1255, 990, 1420, 1062)  # 1920x1080 reference pixels, archive scale 1.0
MAGAZINE_WINDOW = (10, 8, 80, 62)  # x0, y0, x1, y1 inside the ammo crop
# Reserve count: the small digits right of the bullet icon (x ~100-120, y ~29-43);
# the window starts after the icon so its bars are not taken for digits.
RESERVE_WINDOW = (96, 22, 140, 50)
RESERVE_GLYPH_HEIGHT = (12, 16)
RESERVE_MAX_GAP = 5  # px between the digits of one number
MAX_RESERVE = 200
GLYPH_SIZE = (14, 20)  # width, height after normalisation
MIN_GLYPH_HEIGHT, MAX_GLYPH_HEIGHT = 22, 38
DIGIT_MIN_SCORE = 0.75
DIGIT_MIN_MARGIN = 0.05
MAX_MAGAZINE = 100
RIGHT_EDGE_MIN = 54  # the last digit ends at x ~60 in the magazine window
TEMPLATE_NAME = "ammo_digits_v1.npz"
MANIFEST_NAME = "ammo_digits_v1.json"
_TOPHAT = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
_RESERVE_TOPHAT = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))

Box = tuple[int, int, int, int]


class AmmoTemplatesUnavailable(RuntimeError):
    """The private magazine-digit templates have not been built on this machine."""


def _bright_mask(gray: np.ndarray) -> np.ndarray:
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, _TOPHAT)
    return ((tophat > 40) & (gray > 170)).astype(np.uint8)


def left_neighbour_occupied(gray: np.ndarray, box: Box) -> bool:
    """A digit-height bright stroke just left of a lone glyph: a leading digit
    that failed segmentation (occluded or merged), so the value would be cut."""
    x, y, w, h = box
    region = _bright_mask(gray)[y:y + h, max(0, x - 24):max(0, x - 2)]
    if region.size == 0:
        return False
    return bool((region.sum(axis=0) >= 0.5 * h).any())


def magazine_glyphs(crop: np.ndarray) -> tuple[np.ndarray, list[Box]]:
    x0, y0, x1, y1 = MAGAZINE_WINDOW
    full: np.ndarray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = full[y0:y1, x0:x1]
    mask = _bright_mask(gray)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    boxes = []
    for index in range(1, count):
        x, y, w, h, area = (int(v) for v in stats[index])
        if MIN_GLYPH_HEIGHT <= h <= MAX_GLYPH_HEIGHT and 3 <= w <= 26 and area >= 30:
            boxes.append((x, y, w, h))
    boxes.sort()
    return gray, boxes


def _stroke_beside(gray: np.ndarray, boxes: list[Box]) -> bool:
    """A digit-height bright stroke just left of the first or right of the last
    glyph: a digit that failed segmentation (occluded or merged with a bright
    background), so the number would be cut."""
    _, y, _, h = boxes[0]
    bright = (gray[y:y + h] > 170).sum(axis=0) >= 0.5 * h
    first_x = boxes[0][0]
    last_x, _, last_w, _ = boxes[-1]
    left = bright[max(0, first_x - 9):max(0, first_x - 1)]
    right = bright[last_x + last_w + 1:last_x + last_w + 10]
    return bool(left.any() or right.any())


def reserve_glyphs(crop: np.ndarray) -> tuple[np.ndarray, list[Box]]:
    x0, y0, x1, y1 = RESERVE_WINDOW
    full: np.ndarray = crop if crop.ndim == 2 else cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    gray = full[y0:y1, x0:x1]
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, _RESERVE_TOPHAT)
    mask = ((tophat > 35) & (gray > 160)).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    low, high = RESERVE_GLYPH_HEIGHT
    boxes = [(int(x), int(y), int(w), int(h)) for x, y, w, h, area in
             (stats[i] for i in range(1, count))
             if low <= h <= high and 3 <= w <= 12 and area >= 20]
    boxes.sort()
    return gray, boxes


def normalise(gray: np.ndarray, box: Box) -> np.ndarray:
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


@dataclass(frozen=True)
class MagazineReading:
    value: int | None
    glyphs: int  # digit-shaped components seen (0: no ammo HUD visible)
    # Lowest digit template match (normalised correlation): source confidence
    # for the timeline, not a calibrated probability.
    match: float | None = None


def _flatten(templates: np.ndarray) -> np.ndarray:
    if templates.shape != (10, GLYPH_SIZE[1], GLYPH_SIZE[0]):
        raise ValueError("expected 10 digit templates")
    flat = templates.reshape(10, -1).astype(np.float32)
    flat -= flat.mean(axis=1, keepdims=True)
    flat /= np.maximum(np.linalg.norm(flat, axis=1, keepdims=True), 1e-6)
    return flat


def _best(templates: np.ndarray, glyph: np.ndarray) -> tuple[int | None, float]:
    scores = templates @ glyph.reshape(-1)
    order = np.argsort(scores)[::-1]
    best, second = float(scores[order[0]]), float(scores[order[1]])
    if best < DIGIT_MIN_SCORE or best - second < DIGIT_MIN_MARGIN:
        return None, best
    return int(order[0]), best


class AmmoReader:
    """Magazine count (large digits) and, when its templates exist, the reserve
    count (small digits). The reserve changes on a weapon switch, which is how a
    switch is told apart from firing."""

    def __init__(self, templates: np.ndarray, reserve: np.ndarray | None = None) -> None:
        self.templates = _flatten(templates)
        self.reserve_templates = None if reserve is None else _flatten(reserve)

    @classmethod
    def load(cls, cache_dir: Path) -> AmmoReader:
        path = cache_dir / "hud_templates" / TEMPLATE_NAME
        manifest = cache_dir / "hud_templates" / MANIFEST_NAME
        if not path.exists() or not manifest.exists():
            raise AmmoTemplatesUnavailable(f"missing {path}; run build_ammo_templates.py")
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        if meta.get("lineage", {}).get("split") != "TRAIN":
            raise AmmoTemplatesUnavailable(f"{path} has no TRAIN-only lineage; rebuild it")
        if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
            raise AmmoTemplatesUnavailable(f"{path} does not match its manifest")
        with np.load(path) as data:
            return cls(data["digits"], data["reserve"] if "reserve" in data.files else None)

    def digit_scored(self, glyph: np.ndarray) -> tuple[int | None, float]:
        return _best(self.templates, glyph)

    def digit(self, glyph: np.ndarray) -> int | None:
        return self.digit_scored(glyph)[0]

    def read(self, crop: np.ndarray) -> MagazineReading:
        gray, boxes = magazine_glyphs(crop)
        if not 1 <= len(boxes) <= 3:
            return MagazineReading(None, len(boxes))
        last_x, _, last_w, _ = boxes[-1]
        if left_neighbour_occupied(gray, boxes[0]) or last_x + last_w < RIGHT_EDGE_MIN:
            # A digit is missing: the count is right-aligned against the bullet icon.
            return MagazineReading(None, len(boxes))
        scored = [self.digit_scored(normalise(gray, box)) for box in boxes]
        if any(d is None for d, _ in scored):
            return MagazineReading(None, len(boxes))
        value = int("".join(str(d) for d, _ in scored))
        if value > MAX_MAGAZINE:
            return MagazineReading(None, len(boxes))
        return MagazineReading(value, len(boxes), min(m for _, m in scored))

    def read_reserve(self, crop: np.ndarray) -> MagazineReading:
        """Reserve count; ``value`` is None when unread or without reserve templates."""
        gray, boxes = reserve_glyphs(crop)
        if self.reserve_templates is None or not 1 <= len(boxes) <= 3:
            return MagazineReading(None, len(boxes))
        for (x, _, w, _), (next_x, _, _, _) in zip(boxes, boxes[1:], strict=False):
            if next_x - (x + w) > RESERVE_MAX_GAP:
                return MagazineReading(None, len(boxes))
        if _stroke_beside(gray, boxes):
            return MagazineReading(None, len(boxes))
        scored = [_best(self.reserve_templates, normalise(gray, box)) for box in boxes]
        if any(d is None for d, _ in scored):
            return MagazineReading(None, len(boxes))
        value = int("".join(str(d) for d, _ in scored))
        if value > MAX_RESERVE:
            return MagazineReading(None, len(boxes))
        return MagazineReading(value, len(boxes), min(m for _, m in scored))
