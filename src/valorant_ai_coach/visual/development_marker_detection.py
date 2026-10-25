"""Bounded marker appearances without recorder/player role transfer.

Native NCC anchors are preserved. Extra scale and circular rim observations are
unassigned hypotheses, not identified players. This module does not track, infer
view state, interpolate, or qualify a map/reference build.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from .development_marker_proposals import DevelopmentMarkerProposals
from .self_marker import MarkerReferenceInspector

Image = NDArray[Any]
SCALES = (.75, .875, 1., 1.125, 1.25)


def _key(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _iou(a: dict[str, Any], b: dict[str, Any]) -> float:
    ax, ay = a["center_roi_px"]
    aw, ah = a["size_roi_px"]
    bx, by = b["center_roi_px"]
    bw, bh = b["size_roi_px"]
    area = (max(0., min(ax+aw/2, bx+bw/2)-max(ax-aw/2, bx-bw/2))
            * max(0., min(ay+ah/2, by+bh/2)-max(ay-ah/2, by-bh/2)))
    return float(area/(aw*ah+bw*bh-area))


def _groups(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Seed-relative duplicate groups, never transitive center averaging."""
    groups: list[list[dict[str, Any]]] = []
    for point in sorted(raw, key=lambda p: (
            -p["support_similarity"], abs(p["scale"]-1), p["library_index"],
            *p["center_roi_px"])):
        group = next((g for g in groups if math.dist(
            g[0]["center_roi_px"], point["center_roi_px"])
            <= min(*g[0]["size_roi_px"], *point["size_roi_px"])*.25
            and _iou(g[0], point) >= .45), None)
        if group is None:
            groups.append([point])
        else:
            group.append(point)
    return [{**g[0], "supports": g} for g in groups]


class BoundedMarkerDetector:
    """Opt-in ROI proposals with fixed acceptance and explicit search budgets."""

    def __init__(self) -> None:
        self.inspectors = [MarkerReferenceInspector() for _ in range(4)]
        self.last_evidence: dict[str, Any] = {}
        self._shape: tuple[int, int] | None = None
        self._fingerprint: str | None = None

    def _references(self, libraries: list[dict[str, Any]]) -> list[str]:
        fingerprints = []
        for inspector, lib in zip(self.inspectors[:len(libraries)], libraries, strict=True):
            loader = inspector._loader
            if not loader._load(lib["matcher"]):
                raise ValueError("Invalid marker reference library")
            if loader._references[0].shape[0] != loader._references[0].shape[1]:
                raise ValueError("Square marker references required")
            assert loader.reference_fingerprint is not None
            fingerprints.append(loader.reference_fingerprint)
        return fingerprints

    def _model_key(self, libraries: list[dict[str, Any]], refs: list[str]) -> str:
        return _key({"algorithm": "bounded_marker_appearances_v1", "scales": SCALES,
                     "roi_shape": self._shape, "libraries": libraries,
                     "reference_fingerprints": refs,
                     "circle": [1, 8, 80, 14, 5, 11, .5, 12, 40, 120, 15, .2, .1, 3, .1],
                     "limits": [1024, 128, 64, 128], "merge_native_roi_px": 4})

    def verify(self, libraries: list[dict[str, Any]], expected: str) -> None:
        try:
            valid = self._fingerprint == expected == self._model_key(
                libraries, self._references(libraries))
        except (ValueError, TypeError):
            valid = False
        if not valid:
            self._fingerprint = None
            self.last_evidence = {"qualification": "development_only", "ownership": "UNKNOWN",
                                  "reason": "reference_changed"}
            raise ValueError("Reference changed during proposal observation")

    def detect(self, crop: Image, appearance_pool: dict[str, Any]) -> dict[str, Any]:
        self._fingerprint = None
        self.last_evidence = {"qualification": "development_only", "ownership": "UNKNOWN",
                              "reason": "invalid_input"}
        if (not isinstance(crop, np.ndarray) or crop.dtype != np.uint8
                or crop.ndim != 3 or crop.shape[2] != 3
                or min(crop.shape[:2]) < 65 or max(crop.shape[:2]) > 1024):
            raise ValueError("Bounded uint8 BGR minimap ROI required")
        libraries = appearance_pool.get("libraries")
        if (appearance_pool.get("mode") != "appearance_pool_v1"
                or not isinstance(libraries, list) or not 1 <= len(libraries) <= 4
                or any(not isinstance(lib, dict) or lib.get("role") != "appearance_contrast_only"
                       or not isinstance(lib.get("source_id"), str) or not lib["source_id"]
                       or not isinstance(lib.get("matcher"), dict) for lib in libraries)):
            raise ValueError("Explicit bounded marker appearance bank required")
        self._shape = crop.shape[:2]
        refs = self._references(libraries)
        fingerprint = self._model_key(libraries, refs)
        pixel_sha = hashlib.sha256(crop.tobytes()).hexdigest()
        height, width = crop.shape[:2]
        raw: list[dict[str, Any]] = []
        passes = []
        truncated = False
        for scale in SCALES:
            nw, nh = round(width/scale), round(height/scale)
            if max(nw, nh) > 1024 or min(nw, nh) < 65:
                passes.append({"scale": scale, "reason": "scaled_roi_bound"})
                truncated = True
                continue
            target = crop if (nw, nh) == (width, height) else cv2.resize(
                crop, (nw, nh), interpolation=cv2.INTER_AREA if nw < width else cv2.INTER_LINEAR)
            sx, sy = nw/width, nh/height
            for index, (inspector, lib) in enumerate(zip(
                    self.inspectors[:len(libraries)], libraries, strict=True)):
                evidence = inspector.inspect(target, lib["matcher"])
                if (evidence["reason"] != "appearance_comparison_only"
                        or evidence["reference_fingerprint"] != refs[index]):
                    raise ValueError("Reference changed during scale search")
                th, tw = inspector._loader._references[0].shape[:2]
                truncated |= evidence["truncated"]
                passes.append({"scale": scale, "library_index": index,
                               "raw_count": len(evidence["matches"]),
                               "truncated": evidence["truncated"]})
                for p in evidence["matches"]:
                    raw.append({
                        "kind": "ncc_appearance", "scale": scale, "library_index": index,
                        "center_roi_px": [(p["x_roi_norm"]*nw+.5)/sx-.5,
                                          (p["y_roi_norm"]*nh+.5)/sy-.5],
                        "size_roi_px": [tw/sx, th/sy],
                        "support_similarity": max(p["positive_similarity"],
                                                  p["nonself_control_similarity"]),
                        "reference_fingerprint": refs[index],
                    })
        native = _groups([p for p in raw if p["scale"] == 1])
        multiscale = _groups(raw)
        circles, circle_evidence = self._circles(crop)
        truncated |= circle_evidence["truncated"]
        ordered = native+multiscale+circles
        candidates: list[dict[str, Any]] = []
        duplicate_count = 0
        duplicate_associations = []
        overflow_count = 0
        for p in ordered:
            duplicate = next((q for q in candidates if math.dist(
                q["center_roi_px"], p["center_roi_px"]) <= 4), None)
            if duplicate is not None:
                duplicate_count += 1
                duplicate_associations.append({
                    "kept_center_roi_px": duplicate["center_roi_px"],
                    "suppressed_center_roi_px": p["center_roi_px"],
                    "suppressed_kind": p["kind"],
                    "distance_px": math.dist(duplicate["center_roi_px"], p["center_roi_px"]),
                })
                continue
            if len(candidates) == 128:
                overflow_count += 1
                truncated = True
                continue
            x, y = p["center_roi_px"]
            candidates.append({**p, "x_roi_norm": x/width, "y_roi_norm": y/height,
                               "qualification": "development_only", "ownership": "UNKNOWN",
                               "candidate_kind": "unassigned_marker_appearance"})
        self._fingerprint = fingerprint
        self.verify(libraries, fingerprint)
        if hashlib.sha256(crop.tobytes()).hexdigest() != pixel_sha:
            self._fingerprint = None
            raise ValueError("ROI changed during detection")
        self.last_evidence = {
            "qualification": "development_only", "ownership": "UNKNOWN",
            "method": "bounded_marker_appearances_v1", "reference_fingerprint": fingerprint,
            "roi_size_px": [width, height], "roi_pixel_sha256": pixel_sha,
            "scale_passes": passes, "raw_ncc_count": len(raw),
            "ncc_observations": raw,
            "native_groups": len(native), "multiscale_groups": len(multiscale),
            "circle_search": circle_evidence, "duplicates_removed": duplicate_count,
            "duplicate_associations": duplicate_associations,
            "output_count": len(candidates), "overflow_count": overflow_count,
            "search_truncated": truncated, "selected_self_position": None,
            "formal_self_position_fact": None, "development_events": [],
        }
        return {**self.last_evidence, "candidates": candidates}

    @staticmethod
    def _circles(crop: Image) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        smooth = cv2.GaussianBlur(gray, (3, 3), .8)
        found = cv2.HoughCircles(smooth, cv2.HOUGH_GRADIENT, dp=1, minDist=8,
                                 param1=80, param2=14, minRadius=5, maxRadius=11)
        count = 0 if found is None else len(found[0])
        truncated = count > 128
        evidence: dict[str, Any] = {"raw_count": count, "checked_count": min(count, 128)}
        accepted: list[dict[str, Any]] = []
        rejected: dict[str, int] = {}
        observations = []
        gx = cv2.Sobel(smooth, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(smooth, cv2.CV_32F, 0, 1, ksize=3)
        for point in ([] if found is None else found[0][:128]):
            x, y, radius = map(float, point)
            support = BoundedMarkerDetector._circle_support(crop, gray, gx, gy, x, y, radius)
            observations.append({"center_roi_px": [x, y], "radius_px": radius,
                                 "support": support})
            if not support["passed"]:
                reason = support["reason"]
                rejected[reason] = rejected.get(reason, 0)+1
                continue
            accepted.append({"kind": "chromatic_rim_circle", "center_roi_px": [x, y],
                             "size_roi_px": [radius*2+1, radius*2+1],
                             "circle_support": support})
        # Same geometric order used in the development trial. Never self ranking.
        accepted.sort(key=lambda p: (-p["circle_support"]["coherence"], *p["center_roi_px"]))
        truncated |= len(accepted) > 64
        evidence.update(accepted_count=len(accepted), rejected=rejected, truncated=truncated,
                        observations=observations)
        return accepted[:64], evidence

    @staticmethod
    def _circle_support(
        crop: Image, gray: Image, gx: Image, gy: Image,
        x: float, y: float, radius: float,
    ) -> dict[str, Any]:
        half = math.ceil(radius+4)
        if not half <= x < crop.shape[1]-half or not half <= y < crop.shape[0]-half:
            return {"passed": False, "reason": "border"}
        size = half*2+1
        yy, xx = np.indices((size, size))
        dx, dy = xx-half, yy-half
        distance = np.hypot(dx, dy)
        ring = (distance >= radius-1.5) & (distance <= radius+1.5)
        outer = (distance >= radius+2) & (distance <= radius+4)
        inner = distance <= radius*.55
        px = cv2.getRectSubPix(gx, (size, size), (x, y))
        py = cv2.getRectSubPix(gy, (size, size), (x, y))
        energy = px*px+py*py
        denominator = float(energy[ring].sum())
        radial = (px*dx/np.maximum(distance, 1)+py*dy/np.maximum(distance, 1))**2
        coherence = float(radial[ring].sum())/denominator if denominator > 1 else 0.
        texture = float(cv2.getRectSubPix(gray, (size, size), (x, y))[inner].std())
        hsv = cv2.cvtColor(cv2.getRectSubPix(crop, (size, size), (x, y)), cv2.COLOR_BGR2HSV)
        colored = (hsv[:, :, 1] >= 40) & (hsv[:, :, 2] >= 120)
        histogram = np.bincount((hsv[:, :, 0][ring & colored]//10).astype(int), minlength=18)
        smoothed = histogram+np.roll(histogram, 1)+np.roll(histogram, -1)
        hue_bin = int(np.argmax(smoothed))
        difference = np.abs(hsv[:, :, 0].astype(float)-(hue_bin*10+5))
        same = colored & (np.minimum(difference, 180-difference) <= 15)
        coverage = float(same[ring].mean())
        contrast = coverage-float(same[outer].mean())
        quadrants = [float(same[ring & (dx >= 0 if a else dx < 0)
                               & (dy >= 0 if b else dy < 0)].mean())
                     for a, b in [(False, False), (False, True), (True, False), (True, True)]]
        passed = (coherence >= .5 and texture >= 12 and coverage >= .2 and contrast >= .1
                  and sum(q >= .1 for q in quadrants) >= 3)
        return {"passed": passed, "reason": "supported" if passed else "rim_not_supported",
                "radius_px": radius, "coherence": coherence, "inner_texture_std": texture,
                "dominant_hue_bin": hue_bin, "rim_coverage": coverage,
                "outer_contrast": contrast, "quadrants": quadrants}


class DevelopmentDetectedMarkerProposals(DevelopmentMarkerProposals):
    """Three stages: detected appearances, raw geometry, unassigned target.

    The inherited native binding, current-frame calibration and floor checks are
    unchanged. All version-compatible/player positions remain null.
    """

    def __init__(self, map_id: str) -> None:
        super().__init__(map_id)
        self.detector = BoundedMarkerDetector()

    def _inspect_appearances(
        self, crop: Image, libraries: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        result = self.detector.detect(crop, {"mode": "appearance_pool_v1", "libraries": libraries})
        return [{"matches": result["candidates"],
                 "reference_fingerprint": result["reference_fingerprint"],
                 "truncated": result["search_truncated"]}]

    def _verify_appearances(
        self, libraries: list[dict[str, Any]], evidence: list[dict[str, Any]],
    ) -> None:
        self.detector.verify(libraries, evidence[0]["reference_fingerprint"])

    def observe(
        self, frame: Image, *, sample: dict[str, Any], minimap_roi: list[float],
        appearance_pool: dict[str, Any], calibration_profile: dict[str, Any],
        context_eligible: bool,
    ) -> dict[str, Any]:
        result = super().observe(
            frame, sample=sample, minimap_roi=minimap_roi, appearance_pool=appearance_pool,
            calibration_profile=calibration_profile, context_eligible=context_eligible)
        result["detector_evidence"] = self.detector.last_evidence
        return result
