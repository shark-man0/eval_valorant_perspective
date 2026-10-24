"""Opt-in primary-style shape rejection; never recorder ownership.

Cross-recording positive/control portrait roles are not stable actor labels.
This additional gate can reject a selected texture without primary-style ring
support. It does not choose a replacement, recover missed icons, or establish
that a ring belongs to the recorder. Existing pool behavior is unchanged.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .development_appearance_pool import ContrastiveAppearancePool
from .self_marker import MarkerPosition


def portrait_annulus_evidence(crop: NDArray[Any], center: tuple[float, float],
                             size: int) -> dict[str, Any]:
    """Measure the same fixed shape criteria as PortablePortraitTracker.

    The caller supplies observed pixel coordinates, not a semantic self label.
    Scores are raw measurements, not probabilities or calibrated identity cues.
    """
    unavailable = {"supported": False, "reason": "annulus_geometry_unavailable"}
    if (not isinstance(size, int) or isinstance(size, bool) or not 9 <= size <= 65
            or size % 2 != 1 or not isinstance(crop, np.ndarray)
            or crop.dtype != np.uint8 or crop.ndim != 3 or crop.shape[2] != 3
            or len(center) != 2 or any(not isinstance(x, (int, float))
                or isinstance(x, bool) or not math.isfinite(x) for x in center)):
        return unavailable
    cx, cy = (round(v) for v in center)
    half = size//2
    if not (half <= cx < crop.shape[1]-half and half <= cy < crop.shape[0]-half):
        return unavailable
    patch = crop[cy-half:cy+half+1, cx-half:cx+half+1]
    yy, xx = np.indices((size, size))
    radius = np.hypot(xx-half, yy-half)
    annulus = (radius >= size*.35) & (radius <= size*.53)
    inner = radius < size*.29
    channels = patch.astype(np.float32)
    chroma = np.minimum(channels[:, :, 2], channels[:, :, 1])-channels[:, :, 0]
    coverage = float((chroma[annulus] > 15).mean())
    quadrants = [float((chroma[annulus & (xx >= half if hx else xx < half)
                              & (yy >= half if hy else yy < half)] > 15).mean())
                 for hx, hy in [(False, False), (False, True), (True, False), (True, True)]]
    texture = float(cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)[inner].std())
    return {
        "supported": coverage >= .25 and sum(q >= .15 for q in quadrants) >= 3 and texture >= 12,
        "reason": "observed_annulus_and_texture", "coverage": coverage,
        "quadrants": quadrants, "inner_texture_std": texture,
        "semantic_recorder_link": False, "qualification": "development_only",
    }


class AnnulusValidatedAppearancePool(ContrastiveAppearancePool):
    """Conservative optional veto, with no fallback or maximum-score ownership."""

    @property
    def reference_fingerprint(self) -> str | None:
        fingerprint = super().reference_fingerprint
        return hashlib.sha256(("appearance_pool_annulus_v1:"+fingerprint).encode()).hexdigest() \
            if fingerprint is not None else None

    def observe(
        self, crop: NDArray[Any], time_sec: float, spec: dict[str, Any], *,
        ownership_eligible: bool,
    ) -> MarkerPosition:
        if not isinstance(spec, dict) or spec.get("mode") != "appearance_pool_annulus_v1":
            self.reset()
            self._pool_fingerprint = None
            self.last_evidence = {"qualification": "development_only", "ownership": "UNKNOWN",
                                  "semantic_recorder_link": False}
            return MarkerPosition("unknown", "invalid_annulus_pool")
        result = super().observe(crop, time_sec, {**spec, "mode": "appearance_pool_v1"},
                                 ownership_eligible=ownership_eligible)
        self.last_evidence.update(policy="appearance_pool_annulus_v1",
                                  reference_fingerprint=self.reference_fingerprint)
        if result.x_roi_norm is None:
            return result
        assert result.y_roi_norm is not None and self._selected is not None
        selected = self.members[self._selected[0]]
        h, w = selected._references[0].shape[:2]
        evidence = (portrait_annulus_evidence(
            crop, (result.x_roi_norm*crop.shape[1], result.y_roi_norm*crop.shape[0]), w)
            if h == w else {"supported": False, "reason": "annulus_geometry_unavailable"})
        self.last_evidence["annulus"] = evidence
        if not evidence["supported"]:
            self.last_evidence["rejected_appearance"] = result.to_dict()
            self.reset()
            return MarkerPosition("unknown", "primary_annulus_not_supported",
                                  result.candidate_count)
        return MarkerPosition(result.status, "annulus_supported_appearance_only",
                              result.candidate_count, result.x_roi_norm, result.y_roi_norm,
                              result.appearance_score, result.track_id)
