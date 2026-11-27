"""Opt-in full-frame spectator UI veto, never positive ownership evidence."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from valorant_ai_coach.video.geometry import normalized_roi_bounds


class DevelopmentViewVeto:
    """Match one source-reviewed switch-player glyph at an authored UI location.

    Absence of this pattern cannot establish live/self eligibility. Missing or
    invalid configured references fail closed. Source-specific, unqualified,
    and deliberately separate from the Production HUD recognizer.
    """

    def __init__(self) -> None:
        self._key: str | None = None
        self._template: NDArray[Any] | None = None

    def inspect(
        self, frame: NDArray[Any], spec: Any, *, feature_mode: str = "gray_v1",
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "qualification": "development_only", "ownership": "UNKNOWN",
            "status": "disabled", "veto": False, "similarity": None,
            "reference_sha256": None,
        }
        if spec is None:
            return result
        result.update(status="unavailable", veto=True)
        if (not isinstance(feature_mode, str)
                or feature_mode not in {"gray_v1", "positive_contrast_v1"}):
            return result
        if (not isinstance(frame, np.ndarray) or frame.ndim != 3 or frame.shape[2] != 3
                or frame.dtype != np.uint8 or min(frame.shape[:2]) <= 0):
            return result
        if not isinstance(spec, dict) or spec.get("mode") != "spectator_switch_v1":
            return result
        bounds = normalized_roi_bounds(spec.get("roi"), frame.shape[1], frame.shape[0])
        size = spec.get("reference_frame_size_px")
        if (bounds is None or not isinstance(size, list) or len(size) != 2
                or any(not isinstance(v, int) or isinstance(v, bool) or not 64 <= v <= 4096
                       for v in size)):
            return result
        author_bounds = normalized_roi_bounds(spec.get("roi"), *size)
        if author_bounds is None:
            return result
        al, at, ar, ab = author_bounds
        if (ar-al)*(ab-at) > 250_000:
            return result
        try:
            with Path(spec["template_path"]).open("rb") as source:
                content = source.read(1_000_001)
        except (KeyError, OSError, TypeError, ValueError):
            return result
        if (len(content) > 1_000_000 or len(content) < 24
                or content[:16] != b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"):
            return result
        w, h = int.from_bytes(content[16:20]), int.from_bytes(content[20:24])
        if not (8 <= w <= 512 and 8 <= h <= 128 and w <= ar-al and h <= ab-at):
            return result
        key = hashlib.sha256(content).hexdigest()
        result["reference_sha256"] = key
        cache_key = key + ":" + feature_mode
        if self._key != cache_key:
            self._key, self._template = None, None
            template = cv2.imdecode(np.frombuffer(content, np.uint8), cv2.IMREAD_GRAYSCALE)
            if template is None or float(template.std()) < 12:
                return result
            if feature_mode == "positive_contrast_v1":
                template = _positive_contrast(template)
                if float(template.std()) < 1:
                    return result
            self._template, self._key = template, cache_key
        assert self._template is not None
        left, top, right, bottom = bounds
        crop = cv2.cvtColor(frame[top:bottom, left:right], cv2.COLOR_BGR2GRAY)
        crop = cv2.resize(crop, (ar-al, ab-at), interpolation=cv2.INTER_AREA)
        if feature_mode == "positive_contrast_v1":
            crop = _positive_contrast(crop)
        scores = cv2.matchTemplate(crop, self._template, cv2.TM_CCOEFF_NORMED)
        score = float(np.max(np.clip(np.nan_to_num(
            scores, nan=-1, posinf=-1, neginf=-1), -1, 1)))
        result.update(similarity=score, veto=score >= .90,
                      status="spectator_ui" if score >= .90 else "not_detected")
        return result


def _positive_contrast(gray: NDArray[Any]) -> NDArray[Any]:
    """Keep locally bright strokes, suppress broad background lighting.

    Opt-in development feature, not an ownership or semantic-text detector.
    The fixed same-pixel kernels assume the reviewed reference frame geometry.
    """
    pixels = gray.astype(np.float32)
    strokes = np.maximum(pixels - cv2.GaussianBlur(pixels, (0, 0), 3), 0)
    result: NDArray[Any] = cv2.GaussianBlur(strokes, (3, 3), .6)
    return result
