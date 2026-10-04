"""Current-frame Report presence from independent static header supports.

This witness can only add an exclusion. It never establishes Report absence,
self-HUD identity or self-HUD loss. Reference assets remain profile-specific.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[np.uint8]


@dataclass(frozen=True)
class ReportHeader:
    reference: Image
    mask: Image
    regions: Image
    input_shape: tuple[int, int]
    reference_x: float
    threshold: float

    def validate(self) -> None:
        if (
            self.reference.ndim != 2
            or self.reference.dtype != np.uint8
            or self.mask.shape != self.reference.shape
            or self.regions.shape != self.reference.shape
            or self.mask.dtype != np.uint8
            or self.regions.dtype != np.uint8
            or not set(np.unique(self.mask)).issubset({0, 255})
            or set(np.unique(self.regions)) != {0, 1, 2}
            or np.any((self.mask > 0) & (self.regions == 0))
            or type(self.threshold) not in (int, float)
            or not np.isfinite(self.threshold)
            or not 0.90 <= self.threshold <= 1.0
            or type(self.reference_x) not in (int, float)
            or not np.isfinite(self.reference_x)
            or not 0 <= self.reference_x <= 1
            or len(self.input_shape) != 2
            or any(type(x) is not int or x <= 0 for x in self.input_shape)
        ):
            raise ValueError("invalid Report header contract")
        height, width = self.input_shape
        rh, rw = self.reference.shape
        origin = round(self.reference_x * width)
        if rh < 8 or rh >= height or origin < 2 or origin + rw + 2 > width:
            raise ValueError("Report header search exceeds configured geometry")
        boxes = []
        for group in (1, 2):
            selected = (self.mask > 0) & (self.regions == group)
            ys, xs = np.nonzero(selected)
            if (
                len(xs) < 32
                or np.ptp(xs) < 8
                or np.ptp(ys) < 8
                or float(self.reference[selected].std()) < 5
            ):
                raise ValueError("insufficient independent Report support")
            boxes.append((int(xs.min()), int(xs.max())))
        if not (boxes[0][1] + 16 < boxes[1][0] or boxes[1][1] + 16 < boxes[0][0]):
            raise ValueError("Report supports must be spatially independent")


def _curve(image: Image, template: Image, mask: NDArray[np.bool_]) -> NDArray[np.float64]:
    src = image.astype(np.float32)
    m = mask.astype(np.float32)
    t = template.astype(np.float32)
    count = float(m.sum())
    ti = t * m
    si = cv2.matchTemplate(src, m, cv2.TM_CCORR)[:, 0].astype(np.float64)
    si2 = cv2.matchTemplate(src * src, m, cv2.TM_CCORR)[:, 0].astype(np.float64)
    sti = cv2.matchTemplate(src, ti, cv2.TM_CCORR)[:, 0].astype(np.float64)
    st = float(ti.sum())
    vt = max(0.0, float((t * ti).sum()) - st * st / count)
    vi = np.maximum(0.0, si2 - si * si / count)
    denominator = np.sqrt(vi * vt)
    result = np.full(vi.shape, -1.0, dtype=np.float64)
    valid = (vi / count >= 25) & (denominator > 1e-9)
    result[valid] = (sti[valid] - st * si[valid] / count) / denominator[valid]
    return np.clip(result, -1.0, 1.0)


def _exact(reference: Image, observed: Image, mask: NDArray[np.bool_]) -> float:
    a = reference[mask].astype(np.float64)
    b = observed[mask].astype(np.float64)
    if float(b.std()) < 5:
        return -1.0
    a -= a.mean()
    b -= b.mean()
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(a @ b / denominator) if denominator > 1e-9 else -1.0


def report_header_evidence(image: Image, model: ReportHeader) -> dict[str, Any]:
    """Both groups must match under a shared bounded horizontal/local ROI pose."""
    if image.ndim == 3:
        image = np.asarray(cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), dtype=np.uint8)
    if image.dtype != np.uint8 or image.shape != model.input_shape:
        return {"present": None, "score": 0.0, "reason": "geometry_invalid"}
    model.validate()
    height, width = image.shape
    rh, _ = model.reference.shape
    origin = round(model.reference_x * width)
    groups = []
    for group in (1, 2):
        selected = (model.mask > 0) & (model.regions == group)
        xs = np.nonzero(selected)[1]
        x1, x2 = int(xs.min()), int(xs.max() + 1)
        groups.append((model.reference[:, x1:x2], selected[:, x1:x2], x1, x2))
    scores = np.full((height - rh + 1, 5, 2), -1.0, dtype=np.float64)
    for offset_index, dx in enumerate(range(-2, 3)):
        for group_index, (template, mask, x1, x2) in enumerate(groups):
            crop = image[:, origin + dx + x1 : origin + dx + x2]
            scores[:, offset_index, group_index] = _curve(crop, template, mask)
    joint = scores.min(axis=2)
    best_row, best_offset = np.unravel_index(int(joint.argmax()), joint.shape)
    dy = int(best_row)
    dx = int(best_offset) - 2
    # Recompute the winning pose in float64, including near-threshold decisions.
    exact = [
        _exact(template, image[dy : dy + rh, origin + dx + x1 : origin + dx + x2], mask)
        for template, mask, x1, x2 in groups
    ]
    confidence = max(0.0, min(1.0, min(exact)))
    return {
        "present": True if confidence >= model.threshold else None,
        "score": confidence,
        "reason": "static_header_support"
        if confidence >= model.threshold
        else "insufficient_or_contradictory_support",
    }
