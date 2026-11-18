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
GLYPH_SIZE = (14, 20)  # width, height after normalisation
MIN_GLYPH_HEIGHT, MAX_GLYPH_HEIGHT = 22, 38
DIGIT_MIN_SCORE = 0.75
DIGIT_MIN_MARGIN = 0.05
MAX_MAGAZINE = 100
RIGHT_EDGE_MIN = 54  # the last digit ends at x ~60 in the magazine window
TEMPLATE_NAME = "ammo_digits_v1.npz"
MANIFEST_NAME = "ammo_digits_v1.json"
_TOPHAT = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))

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


class AmmoReader:
    def __init__(self, templates: np.ndarray) -> None:
        if templates.shape != (10, GLYPH_SIZE[1], GLYPH_SIZE[0]):
            raise ValueError("expected 10 digit templates")
        flat = templates.reshape(10, -1).astype(np.float32)
        flat -= flat.mean(axis=1, keepdims=True)
        flat /= np.maximum(np.linalg.norm(flat, axis=1, keepdims=True), 1e-6)
        self.templates = flat

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
            return cls(data["digits"])

    def digit(self, glyph: np.ndarray) -> int | None:
        scores = self.templates @ glyph.reshape(-1)
        order = np.argsort(scores)[::-1]
        best, second = float(scores[order[0]]), float(scores[order[1]])
        if best < DIGIT_MIN_SCORE or best - second < DIGIT_MIN_MARGIN:
            return None
        return int(order[0])

    def read(self, crop: np.ndarray) -> MagazineReading:
        gray, boxes = magazine_glyphs(crop)
        if not 1 <= len(boxes) <= 3:
            return MagazineReading(None, len(boxes))
        last_x, _, last_w, _ = boxes[-1]
        if left_neighbour_occupied(gray, boxes[0]) or last_x + last_w < RIGHT_EDGE_MIN:
            # A digit is missing: the count is right-aligned against the bullet icon.
            return MagazineReading(None, len(boxes))
        digits = [self.digit(normalise(gray, box)) for box in boxes]
        if any(d is None for d in digits):
            return MagazineReading(None, len(boxes))
        value = int("".join(str(d) for d in digits))
        return MagazineReading(value if value <= MAX_MAGAZINE else None, len(boxes))
