"""Opt-in appearance positions on a minimap ROI, never qualified gameplay facts.

References require full-frame source review. A matching portrait is still only
an identity hypothesis: spectator views can show the very same portrait. This
module therefore requires external ownership eligibility and reports UNKNOWN
identity even when it can measure and track an appearance position.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

Image = NDArray[Any]


@dataclass(frozen=True)
class MarkerPosition:
    status: str
    reason: str
    candidate_count: int = 0
    x_roi_norm: float | None = None
    y_roi_norm: float | None = None
    appearance_score: float = 0.0
    track_id: int | None = None
    identity: str = "UNKNOWN"
    qualification: str = "development_only"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SelfMarkerTracker:
    """Fixed-scale textured template proposals with uniqueness and gap guards.

    No nearest-neighbor identity recovery, interpolation, or inferred motion.
    Coordinates describe the supplied ROI, not a normalized map canvas.
    Positive and nonself controls have identical odd dimensions. Limits bound
    CPU/memory even for an invalid profile. Thresholds are similarity gates,
    not empirical probabilities or independent qualification.
    """

    def __init__(self) -> None:
        self._key: tuple[str, ...] | None = None
        self._references: list[Image] = []
        self._negatives: list[Image] = []
        self._previous: tuple[float, tuple[float, float], int] | None = None
        self._next_id = 0
        self._shape: tuple[int, ...] | None = None
        self._mask: Image | None = None

    def reset(self) -> None:
        self._previous = None

    def _load(self, spec: dict[str, Any]) -> bool:
        if not isinstance(spec, dict):
            return False
        positive = spec.get("positive_templates", [])
        negative = spec.get("negative_templates", [])
        mode = spec.get("mode")
        if (
            not isinstance(mode, str) or mode not in {"appearance_v1", "portrait_v2"}
            or not isinstance(positive, list) or not isinstance(negative, list)
            or not 1 <= len(positive) <= 4 or not 1 <= len(negative) <= 8
            or any(not isinstance(p, str) or not p for p in positive + negative)
        ):
            return False
        contents = []
        try:
            for path in positive + negative:
                # Bounded reads, including on cache hits: a path/mtime is not
                # evidence that the reference pixels are unchanged.
                with Path(path).open("rb") as source:
                    content = source.read(1_000_001)
                if len(content) > 1_000_000:
                    return False
                contents.append(content)
        except (OSError, ValueError):
            self._key, self._references, self._negatives = None, [], []
            return False
        key = ((mode,) + tuple(positive) + ("",) + tuple(negative)
               + tuple(hashlib.sha256(content).hexdigest() for content in contents))
        if key == self._key:
            return bool(self._references)
        self.reset()
        self._key, self._references, self._negatives = key, [], []
        images = []
        for content in contents:
            if len(content) < 24 or content[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR":
                return False
            width, height = int.from_bytes(content[16:20]), int.from_bytes(content[20:24])
            if not (9 <= height <= 65 and 9 <= width <= 65 and height % 2 and width % 2):
                return False
            image = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                return False
            h, w = image.shape[:2]
            if not (9 <= h <= 65 and 9 <= w <= 65 and h % 2 and w % 2):
                return False
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            if float(gray.std()) < 12 or float(cv2.Laplacian(gray, cv2.CV_32F).var()) < 100:
                return False
            images.append(image)
        if any(image.shape != images[0].shape for image in images):
            return False
        self._references = images[:len(positive)]
        self._negatives = images[len(positive):]
        self._mask = None
        if spec["mode"] == "portrait_v2":
            h, w = images[0].shape[:2]
            self._mask = np.zeros((h, w), np.uint8)
            cv2.circle(self._mask, (w//2, h//2), round(min(w, h)*.35), 255, -1)
        return True

    def _scores(self, image: Image, template: Image) -> Image:
        if self._mask is None:
            return cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
        return cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED, mask=self._mask)

    def observe(
        self, crop: Image, time_sec: float, spec: dict[str, Any], *, ownership_eligible: bool
    ) -> MarkerPosition:
        def unknown(reason: str, count: int = 0) -> MarkerPosition:
            self.reset()
            return MarkerPosition("unknown", reason, count)

        if not ownership_eligible:
            return unknown("ownership_blocked")
        try:
            valid_time = math.isfinite(time_sec) and time_sec >= 0
        except (TypeError, ValueError):
            valid_time = False
        if not valid_time:
            return unknown("invalid_time")
        if not isinstance(crop, np.ndarray):
            return unknown("invalid_roi")
        if not self._load(spec):
            return unknown("invalid_reference_profile")
        h, w = self._references[0].shape[:2]
        if (
            crop.dtype != np.uint8 or crop.ndim != 3 or crop.shape[2] != 3
            or crop.shape[0] < h or crop.shape[1] < w
        ):
            return unknown("invalid_roi")
        if self._shape != crop.shape:
            self.reset()
            self._shape = crop.shape
        scores = np.maximum.reduce([
            self._scores(crop, reference)
            for reference in self._references
        ])
        scores = np.clip(np.nan_to_num(scores, nan=-1, posinf=-1, neginf=-1), -1, 1)
        _, best, _, peak = cv2.minMaxLoc(scores)
        if best < 0.80:
            return unknown("appearance_below_threshold")
        x, y = peak
        # A spatially distinct second peak must also lose by a margin. Do not
        # choose an arbitrary icon using a historical expected position.
        suppressed = scores.copy()
        suppressed[max(0, y-h//2):y+h//2+1, max(0, x-w//2):x+w//2+1] = -1
        second = float(suppressed.max())
        maxima = cv2.dilate(scores, np.ones((h, w), np.uint8))
        peaks = ((scores >= 0.80) & (scores >= maxima)).astype(np.uint8)
        count = int(cv2.connectedComponents(peaks)[0]) - 1
        if second >= 0.80 or best - second < 0.12:
            return unknown("appearance_ambiguous", count)
        patch = crop[y:y+h, x:x+w]
        nonself = max(
            float(self._scores(patch, ref)[0, 0])
            for ref in self._negatives
        )
        if not math.isfinite(nonself) or best - nonself < 0.12:
            return unknown("nonself_not_separated", count)
        point = ((x + w//2) / crop.shape[1], (y + h//2) / crop.shape[0])
        previous = self._previous
        if previous is not None:
            dt = time_sec - previous[0]
            if not 0 < dt <= 0.3:
                self.reset()
                previous = None
            elif math.dist(point, previous[1]) / dt > 0.4:
                return unknown("position_jump", count)
        if previous is None:
            identifier = self._next_id
            self._next_id += 1
            streak = 1
        else:
            identifier = self._next_id - 1
            streak = previous[2] + 1
        self._previous = time_sec, point, streak
        return MarkerPosition(
            "tracked" if streak >= 3 else "candidate", "appearance_only", count,
            point[0], point[1], float(best), identifier,
        )
