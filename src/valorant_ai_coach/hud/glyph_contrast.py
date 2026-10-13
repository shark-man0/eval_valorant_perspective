"""Additional per-glyph contrast rejection; never infer text or ownership alone."""
from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .weapon_identity import masked_score

ImageU8 = NDArray[np.uint8]
METHOD = 'glyph_local_contrast_v1'


class GlyphContrastGuard:
    """Compare every reference glyph's foreground and internal negative space.

    Current pixels are grayscale, not thresholded as opaque white. All eroded
    negative-space pixels are retained. Small letter holes use fewer partitions
    while preserving the same minimum population and NCC floor.
    """

    def __init__(self, reference: ImageU8) -> None:
        if reference.dtype != np.uint8 or reference.ndim != 2 or not reference.size:
            raise ValueError('glyph contrast requires a nonempty grayscale reference')
        self.reference = reference.copy()
        _, _, stats, _ = cv2.connectedComponentsWithStats(
            (reference >= 210).astype(np.uint8) * 255, connectivity=8,
        )
        boxes = sorted(
            (max(0, int(x)-1), max(0, int(y)-1),
             min(reference.shape[1], int(x+w)+1), min(reference.shape[0], int(y+h)+1))
            for x, y, w, h, area in stats[1:]
            if area >= 32 and w >= 3 and h >= reference.shape[0] * .4
        )
        if len(boxes) < 3:
            raise ValueError('glyph contrast requires complete reference glyph groups')
        self.boxes = tuple(boxes)
        self.parts: list[tuple[ImageU8, NDArray[np.bool_], NDArray[np.bool_],
                               tuple[ImageU8, ...]]] = []
        kernel = np.ones((3, 3), np.uint8)
        for x1, y1, x2, y2 in boxes:
            ref = reference[y1:y2, x1:x2].copy()
            foreground = (ref >= 210).astype(np.uint8)
            core = cv2.erode(foreground, kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0)
            hull = np.zeros_like(foreground)
            points = np.argwhere(foreground > 0)[:, ::-1].astype(np.int32)
            cv2.fillConvexPoly(hull, cv2.convexHull(points), 1)
            background = cv2.erode(
                (hull.astype(bool) & ~foreground.astype(bool)).astype(np.uint8),
                kernel, borderType=cv2.BORDER_CONSTANT, borderValue=0,
            )
            indices = np.flatnonzero(background)
            count = min(3, len(indices)//32)
            if np.count_nonzero(core) < 32 or count < 1:
                raise ValueError('glyph contrast has insufficient foreground/negative space')
            masks: list[ImageU8] = []
            for group in np.array_split(indices, count):
                mask = core.copy()
                mask.flat[group] = 1
                masks.append(np.asarray(mask * 255, dtype=np.uint8))
            self.parts.append((ref, core.astype(bool), background.astype(bool), tuple(masks)))

    def measure(self, image: ImageU8) -> dict[str, Any]:
        if (image.dtype != np.uint8 or image.ndim not in (2, 3)
                or image.ndim == 3 and image.shape[2] != 3):
            return {'method': METHOD, 'score': 0.0, 'glyphs': [], 'reason': 'invalid_image'}
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
        if gray.dtype != np.uint8 or gray.shape != self.reference.shape:
            return {'method': METHOD, 'score': 0.0, 'glyphs': [], 'reason': 'shape_mismatch'}
        glyphs: list[dict[str, Any]] = []
        for index, (box, part) in enumerate(zip(self.boxes, self.parts, strict=True)):
            x1, y1, x2, y2 = box
            ref, foreground, background, masks = part
            actual = gray[y1:y2, x1:x2]
            scores = [masked_score(cv2.GaussianBlur(ref, (3, 3), 0),
                                   cv2.GaussianBlur(actual, (3, 3), 0), mask) for mask in masks]
            polarity = float(actual[foreground].mean()) > float(actual[background].mean())
            glyphs.append({
                'glyph_index': index, 'box': list(box), 'group_ncc': scores,
                'foreground_population': int(np.count_nonzero(foreground)),
                'negative_space_population': int(np.count_nonzero(background)),
                'polarity_positive': polarity, 'score': min(scores) if polarity else 0.0,
            })
        return {'method': METHOD, 'score': min(g['score'] for g in glyphs), 'glyphs': glyphs}

    def score(self, image: ImageU8) -> float:
        return float(self.measure(image)['score'])
