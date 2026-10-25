"""Opt-in marker screening and circle-center hypotheses, never player identity.

The screen only avoids a library search when its approximate correlation plus
a wide numerical allowance is below acceptance. Surviving libraries use the
unchanged inspector. This backend is development-only and must be compared on
the actual input/OpenCV build; it is not a certified floating-point bound.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

import cv2
import numpy as np

from .development_marker_detection import (
    BoundedMarkerDetector,
    DevelopmentDetectedMarkerProposals,
    Image,
    _key,
)
from .self_marker import MarkerReferenceInspector


class _FrameScreen:
    def __init__(self) -> None:
        self.begin()

    def clear(self) -> None:
        self.key: tuple[Any, ...] | None = None
        self.energy: dict[tuple[Any, ...], tuple[Image, Image, int]] = {}

    def begin(self) -> None:
        self.clear()
        self.stats = {"skipped": 0, "exact": 0, "screens": 0, "energy_builds": 0}

    def moments(self, crop: Image, mask: Image) -> tuple[Image, Image, int]:
        key = (crop.shape, hashlib.sha256(crop.tobytes()).digest())
        if key != self.key:
            self.clear()
            self.key = key
        mk = (mask.shape, mask.tobytes())
        if mk in self.energy:
            return self.energy[mk]
        self.stats["energy_builds"] += 1
        height, width = mask.shape
        oh, ow = crop.shape[0]-height+1, crop.shape[1]-width+1
        # The bounded ROI's per-channel intensity integral is below 2**31.
        # Squares need float64, but no persistent float64 image copy is needed.
        integral = cv2.integral(crop, sdepth=cv2.CV_32S)
        integral2 = cv2.integral(np.square(crop, dtype=np.float64))
        total = np.zeros((oh, ow, 3), np.float64)
        squared = np.zeros((oh, ow), np.float64)
        # Circular binary masks have one contiguous run per row. These sums of
        # uint8 values and squares are exact integers within float64 range.
        for y in range(height):
            columns = np.flatnonzero(mask[y])
            if not len(columns):
                continue
            a, b = int(columns[0]), int(columns[-1])+1
            if not np.all(mask[y, a:b]):
                raise ValueError("Contiguous binary circle mask required")
            total += (integral[y+1:y+1+oh, b:b+ow]-integral[y:y+oh, b:b+ow]
                      - integral[y+1:y+1+oh, a:a+ow]+integral[y:y+oh, a:a+ow])
            squared += (integral2[y+1:y+1+oh, b:b+ow]-integral2[y:y+oh, b:b+ow]
                        - integral2[y+1:y+1+oh, a:a+ow]
                        + integral2[y:y+oh, a:a+ow]).sum(axis=2)
        del integral, integral2
        count = int(np.count_nonzero(mask))
        energy = count*squared-(total*total).sum(axis=2)
        if not count or not np.isfinite(energy).all() or float(energy.min()) < 0:
            raise ValueError("Invalid frame-local moments")
        self.energy[mk] = total, energy, count
        return self.energy[mk]

    def possible(self, crop: Image, loader: Any) -> bool:
        self.stats["screens"] += 1
        if loader._mask is None:
            return True
        mask = (loader._mask > 0).astype(np.uint8)
        total, energy, count = self.moments(crop, mask)
        valid = energy > 0
        upper = np.full(energy.shape, -1., np.float64)
        for reference in loader._references+loader._negatives:
            masked = reference*mask[:, :, None]
            sums = masked.sum(axis=(0, 1), dtype=np.float64)
            reference_energy = (count*(masked.astype(np.float64)**2).sum()
                                - (sums*sums).sum())
            if not math.isfinite(reference_energy) or reference_energy <= 0:
                return True
            denominator = np.sqrt(energy*reference_energy)
            dot = cv2.matchTemplate(crop, masked, cv2.TM_CCORR).astype(np.float64)
            numerator = count*dot-(total*sums).sum(axis=2)
            if not np.isfinite(numerator).all():
                return True
            # Deliberately loose allowance for correlation-map rounding. This
            # is a measured screening backend, not an analytic OpenCV guarantee.
            error = 64*float(np.spacing(np.float32(count*3*255**2)))*count
            bound = np.full(energy.shape, -1., np.float64)
            bound[valid] = (numerator[valid]+error)/denominator[valid]+.01
            upper = np.maximum(upper, bound)
        return bool(float(upper.max()) >= .80)


class _ScreenInspector(MarkerReferenceInspector):
    def __init__(self, shared: _FrameScreen) -> None:
        super().__init__()
        self.shared = shared

    def inspect(self, crop: Image, spec: dict[str, Any]) -> dict[str, Any]:
        if (isinstance(crop, np.ndarray) and self._loader._load(spec)
                and crop.dtype == np.uint8 and crop.ndim == 3 and crop.shape[2] == 3
                and min(crop.shape[:2]) >= max(self._loader._references[0].shape[:2])):
            try:
                possible = self.shared.possible(crop, self._loader)
            except (ValueError, FloatingPointError):
                possible = True
            if not possible:
                self.shared.stats["skipped"] += 1
                return {"qualification": "development_only", "ownership": "UNKNOWN",
                        "matches": [], "reason": "appearance_comparison_only",
                        "reference_fingerprint": self._loader.reference_fingerprint,
                        "truncated": False}
        self.shared.stats["exact"] += 1
        return super().inspect(crop, spec)


class ScreenedMarkerDetector(BoundedMarkerDetector):
    """Frame-local screen, preserving the original candidate/evidence contract.

    No transform or position is cached. Shared moments live only for the current
    scale's exact pixels/mask and are discarded on every return or exception.
    Execution counters are separate from proposal evidence and acceptance.
    """

    def __init__(self) -> None:
        super().__init__()
        self.screen = _FrameScreen()
        self.inspectors = [_ScreenInspector(self.screen) for _ in range(4)]
        self.execution_evidence: dict[str, Any] = {}

    def detect(self, crop: Image, appearance_pool: dict[str, Any]) -> dict[str, Any]:
        self.screen.begin()
        self.execution_evidence = {}
        try:
            result = super().detect(crop, appearance_pool)
            self.execution_evidence = {
                "backend": "shared_binary_moments_screen_v1",
                "roi_pixel_sha256": result["roi_pixel_sha256"],
                "reference_fingerprint": result["reference_fingerprint"],
                "counters": dict(self.screen.stats), "qualification": "development_only",
                "numerical_backend_qualified": False,
            }
            return result
        finally:
            self.screen.clear()


class QualityMarkerDetector(ScreenedMarkerDetector):
    """Independent proposal method: keep NCC anchors, refine unique circles.

    ALT circle observations do not authenticate a player. Original circles are
    retained even if ALT misses them. Refinement requires mutual uniqueness,
    which prevents two existing hypotheses from being coalesced by one circle.
    """

    def _model_key(self, libraries: list[dict[str, Any]], refs: list[str]) -> str:
        return _key({"base": super()._model_key(libraries, refs),
                     "quality": "mutually_unique_circle_centers_v1",
                     "alt": [1, 5, 100, .75, 5, 11, 128, 64],
                     "association_px": 3, "extra_suppression_px": 4})

    def detect(self, crop: Image, appearance_pool: dict[str, Any]) -> dict[str, Any]:
        try:
            result = super().detect(crop, appearance_pool)
            return self._refine(crop, appearance_pool, result)
        except (ValueError, TypeError, cv2.error):
            self._fingerprint = None
            self.last_evidence = {"reason": "quality_observation_failed", "ownership": "UNKNOWN",
                                  "qualification": "development_only"}
            self.execution_evidence = {}
            raise

    def _refine(
        self, crop: Image, appearance_pool: dict[str, Any], result: dict[str, Any],
    ) -> dict[str, Any]:
        # The parent validates all inputs, references and current pixels first.
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        smooth = cv2.GaussianBlur(gray, (3, 3), .8)
        gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0)
        gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1)
        found = cv2.HoughCircles(smooth, cv2.HOUGH_GRADIENT_ALT, dp=1, minDist=5,
                                 param1=100, param2=.75, minRadius=5, maxRadius=11)
        raw: list[dict[str, Any]] = []
        for p in ([] if found is None else found[0][:128]):
            x, y, radius = map(float, p)
            support = self._circle_support(crop, gray, gx, gy, x, y, radius)
            raw.append({"center_roi_px": [x, y], "radius_px": radius, "support": support})
        supported = [p for p in raw if p["support"]["passed"]]
        alt = supported[:64]
        candidates = result["candidates"]
        original_centers = [p["center_roi_px"] for p in candidates]
        shifts = []
        for candidate, point in zip(candidates, original_centers, strict=True):
            nearby = [p for p in alt if math.dist(point, p["center_roi_px"]) <= 3]
            if candidate["kind"] != "chromatic_rim_circle" or len(nearby) != 1:
                continue
            target = nearby[0]
            if sum(math.dist(p, target["center_roi_px"]) <= 3 for p in original_centers) != 1:
                continue
            candidate["original_center_roi_px"] = point
            candidate["center_roi_px"] = target["center_roi_px"]
            candidate["center_method"] = "mutually_unique_supported_alt_circle"
            candidate["alt_circle_support"] = target["support"]
            candidate["x_roi_norm"] = target["center_roi_px"][0]/crop.shape[1]
            candidate["y_roi_norm"] = target["center_roi_px"][1]/crop.shape[0]
            shifts.append({"original": point, "refined": target["center_roi_px"]})
        suppressed = []
        overflow = 0
        for p in alt:
            nearby = [c for c in candidates if math.dist(
                c["center_roi_px"], p["center_roi_px"]) <= 4]
            if nearby:
                # Preserve alternative evidence without counting it as another
                # known physical marker or averaging two observations.
                suppressed.append({"center_roi_px": p["center_roi_px"],
                                   "nearby_centers": [c["center_roi_px"] for c in nearby],
                                   "same_physical_marker": "UNKNOWN"})
                continue
            if len(candidates) == 128:
                overflow += 1
                continue
            x, y = p["center_roi_px"]
            candidates.append({
                "kind": "supported_alt_circle", "center_roi_px": [x, y],
                "size_roi_px": [p["radius_px"]*2+1]*2, "circle_support": p["support"],
                "x_roi_norm": x/crop.shape[1], "y_roi_norm": y/crop.shape[0],
                "qualification": "development_only", "ownership": "UNKNOWN",
                "candidate_kind": "unassigned_marker_appearance",
            })
        truncated = bool((found is not None and len(found[0]) > 128)
                         or len(supported) > 64 or overflow)
        result.update(method="mutually_unique_circle_centers_v1", output_count=len(candidates),
                      search_truncated=result["search_truncated"] or truncated,
                      center_refinements=shifts, alt_search={
                          "raw_count": 0 if found is None else len(found[0]),
                          "checked_count": len(raw), "supported_count": len(supported),
                          "truncated": truncated, "overflow_count": overflow,
                          "observations": raw, "suppressed_nearby": suppressed,
                      })
        self.verify(appearance_pool["libraries"], result["reference_fingerprint"])
        if hashlib.sha256(crop.tobytes()).hexdigest() != result["roi_pixel_sha256"]:
            self._fingerprint = None
            self.last_evidence = {"reason": "roi_changed", "ownership": "UNKNOWN"}
            raise ValueError("ROI changed during center observation")
        self.last_evidence = {k: v for k, v in result.items() if k != "candidates"}
        return result


class DevelopmentQualityMarkerProposals(DevelopmentDetectedMarkerProposals):
    """Quality detector plus unchanged native binding, geometry and version gates."""

    detector: QualityMarkerDetector

    def __init__(self, map_id: str) -> None:
        super().__init__(map_id)
        self.detector = QualityMarkerDetector()

    def observe(
        self, frame: Image, *, sample: dict[str, Any], minimap_roi: list[float],
        appearance_pool: dict[str, Any], calibration_profile: dict[str, Any],
        context_eligible: bool,
    ) -> dict[str, Any]:
        result = super().observe(
            frame, sample=sample, minimap_roi=minimap_roi, appearance_pool=appearance_pool,
            calibration_profile=calibration_profile, context_eligible=context_eligible)
        result["execution_evidence"] = self.detector.execution_evidence
        return result
